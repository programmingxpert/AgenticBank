window.AudioService = {
  isListening: false,
  ttsEnabled: true,
  synth: window.speechSynthesis,
  stream: null,
  ws: null,
  audioContext: null,
  processor: null,
  
  init() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      console.warn("Audio recording is not supported in this browser.");
    }
  },

  toggleTTS() {
    this.ttsEnabled = !this.ttsEnabled;
    if (!this.ttsEnabled) {
      this.synth.cancel();
    }
    return this.ttsEnabled;
  },

  async listen(onFinal, onInterim, onError, onStart, onEnd) {
    if (this.isListening) {
      this.stopListening();
      return;
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/banking/transcribe/stream`;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.isListening = true;
        if (onStart) onStart();

        // Downsample directly to 16kHz for Vosk
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        const source = this.audioContext.createMediaStreamSource(this.stream);
        
        // Use ScriptProcessor (deprecated but universally supported and fine for POC)
        this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
        
        source.connect(this.processor);
        this.processor.connect(this.audioContext.destination);

        let silenceStart = Date.now();
        let hasSpoken = false;

        this.processor.onaudioprocess = (e) => {
          if (!this.isListening || this.ws.readyState !== WebSocket.OPEN) return;
          
          const inputData = e.inputBuffer.getChannelData(0);
          
          // Calculate volume for silence detection
          let sum = 0;
          for (let i = 0; i < inputData.length; i++) {
            sum += Math.abs(inputData[i]);
          }
          let avg = sum / inputData.length;
          
          if (avg > 0.01) {
            hasSpoken = true;
            silenceStart = Date.now();
          } else {
            // Auto stop after 2s of silence
            if (hasSpoken && (Date.now() - silenceStart > 2000)) {
              this.stopListening();
            }
          }

          // Convert Float32 to Int16 PCM
          const pcmData = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            let s = Math.max(-1, Math.min(1, inputData[i]));
            pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }
          
          this.ws.send(pcmData.buffer);
        };
      };

      this.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.error) {
          if (onError) onError(data.error);
          this.stopListening();
        } else if (data.partial && data.partial.trim().length > 0) {
          if (onInterim) onInterim(data.partial);
        } else if (data.final && data.final.trim().length > 0) {
          if (onFinal) onFinal(data.final);
        }
      };

      this.ws.onerror = (e) => {
        console.error("WebSocket error:", e);
        if (onError) onError("Failed to connect to speech server");
        this.stopListening();
      };
      
      this.ws.onclose = () => {
        this.isListening = false;
        if (onEnd) onEnd();
      };

    } catch (e) {
      console.error("Failed to start recording:", e);
      if (onError) onError(e.message || "Microphone access denied");
    }
  },

  stopListening() {
    this.isListening = false;
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    if (this.ws) {
      if (this.ws.readyState === WebSocket.OPEN) {
        // Send EOF to Vosk
        this.ws.send(new Int16Array(0).buffer);
      }
      this.ws.close();
      this.ws = null;
    }
  },

  speak(text, onEndCallback) {
    if (!this.ttsEnabled || !this.synth) {
      if (onEndCallback) onEndCallback();
      return;
    }
    
    this.synth.cancel();
    
    let cleanText = text
      .replace(/###\s/g, '')
      .replace(/\*\*/g, '')
      .replace(/\*/g, '')
      .replace(/_/g, '')
      .replace(/`/g, '')
      .replace(/\|/g, ', ')
      .replace(/-/g, ' ')
      .replace(/\n+/g, '. ');

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    
    const voices = this.synth.getVoices();
    const preferredVoice = voices.find(v => v.lang.startsWith('en') && v.name.includes('Female')) || voices.find(v => v.lang.startsWith('en'));
    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }
    
    utterance.onend = () => {
      if (onEndCallback) onEndCallback();
    };
    utterance.onerror = () => {
      if (onEndCallback) onEndCallback();
    };
    
    this.synth.speak(utterance);
  }
};

window.addEventListener('load', () => {
  window.AudioService.init();
});
