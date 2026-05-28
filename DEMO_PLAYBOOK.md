# 🏦 AgenticBank AI — The Demo Playbook
### *10 Scenarios That Will Make Your Audience Stop Scrolling*

> Built with **Python · FastAPI · LangGraph · Oracle 26ai · MCP**
> A Cyclic Multi-Agent AI System for Autonomous Banking Operations

---

<br>

## ✦ Before You Demo — The Setup Slide

When you open this app for the first time, you're not looking at a chatbot.  
You're looking at a **living, breathing autonomous banking command center.**

Three things are running simultaneously:
- 🧠 A **LangGraph Supervisor** that dynamically routes your intent to the right specialist AI agent — with no hardcoded rules
- 🔴 A **live WebSocket feed** that pushes real-time events (transactions, fraud alerts, approvals) to the UI as they happen
- 🔌 A **MCP Server** that lets Claude Desktop or any external AI assistant reach directly into the Oracle database and take banking actions with natural language

*This is what AI-first software architecture looks like in 2025.*

---

<br>

## 🎬 SCENARIO 01 — The Social Engineering Attack

**"I just got a call saying my account is under investigation. They asked me to transfer ₹4,800 immediately to protect my funds."**

### What Happens
1. The **Supervisor** reads the message and instantly recognises the fraud-adjacent phrasing — it routes to the **Fraud Detection Agent** before anything else.
2. The Fraud Agent calls `analyze_transactions` — scanning 50 recent transactions for anomalies using a statistical baseline. It finds 3 transactions just below the ₹5 lakh regulatory reporting threshold. **Structuring detected.**
3. It then calls `alert_banker` with `severity: "critical"` — a live push notification fires to the **Banker Command Center** in real time.
4. The response tells the user exactly what's happening: *"This is a social engineering scam. No legitimate bank ever asks you to transfer money to protect your account. We have alerted your branch manager."*
5. The banker sees the alert on their dashboard immediately — **zero human latency between AI detection and human awareness**.

### Why This Wows
This is not a fraud ruleset. There is no `if message contains "investigation" then flag` code anywhere. The LLM reasoned its way to `CRITICAL`, called the right tool, and notified a human — all in one autonomous loop. **That is agentic AI.**

---

<br>

## 🎬 SCENARIO 02 — The Loan That Knows You

**"I want to borrow ₹15 lakhs for a home renovation. What can I get?"**

### What Happens
1. The **LangGraph Supervisor** routes to the **Loan & Credit Agent**.
2. The agent receives a rich context object already populated with the user's profile: credit score (742), annual income (₹19.6L), existing debt load, DTI ratio (22.4%).
3. It calls `calculate_emi` → returns a precise amortization breakdown:
   - **Monthly EMI**: ₹29,847
   - **Total Interest Paid**: ₹2,18,164 over 60 months
   - **Estimated Rate**: 6.25% (dynamically adjusted down because credit score > 700)
4. The agent then calls `submit_loan_application` → the loan is created in Oracle with status `pending_approval` and the approval entry fires a **live WebSocket event** to the Banker Portal.
5. The banker sees the application appear on their dashboard in real time. They can approve it in one click.

### The Line That Lands
> *"This application was evaluated, priced, documented, and escalated to a human decision-maker — in 8 seconds. No forms. No branch visit. No hold music."*

---

<br>

## 🎬 SCENARIO 03 — The Human-in-the-Loop Wall

**"Transfer ₹25,000 to my friend Raj."**

### What Happens
1. The **Transaction Agent** processes the request and calls `transfer_funds`.
2. The system checks: **₹25,000 > ₹10,000 threshold** → the transfer is **halted** and placed into the pending approval queue. The funds do NOT move.
3. A `pending_approval` WebSocket event is emitted — the Banker Portal immediately shows a new card: *"High-value transfer: ₹25,000 from Sarah Mitchell → Raj Kumar. Awaiting authorization."*
4. The user sees: *"Your transfer is queued for banker approval. You'll be notified once it's cleared."*
5. The banker reviews it, types a reviewer note, and clicks **Approve** — the transaction completes and a debit/credit entry is written to Oracle.

### Why This Is the Most Important Slide
This is the entire point of Human-in-the-Loop AI.  
**The AI does the work. The human holds the power.**  
Show this slide to anyone nervous about "AI making financial decisions" and watch the room relax.

---

<br>

## 🎬 SCENARIO 04 — The Compliance Report That Writes Itself

**"Run a full KYC and AML compliance check on this account."**

### What Happens
1. The **Supervisor** routes to the **Compliance Agent**, which simultaneously runs:
   - `verify_kyc` → Identity ✅, Address ✅, Employment ✅, Income ✅, KYC Date: **Jan 10, 2024 — EXPIRED ⚠️**
   - `aml_check` → Scans 50 transactions for structuring patterns (multiple ₹4.8L–₹4.9L transfers deliberately below the ₹5L threshold)
2. It generates a fully formatted compliance report in the chat — complete with a styled table showing every KYC dimension.
3. If structuring is detected: `alert_banker` fires a `critical` severity alert to the Banker Portal and recommends a **Suspicious Activity Report (SAR)** filing.

### The Line That Lands
> *"What used to take a compliance officer 2 hours and a spreadsheet now takes 8 seconds and a single sentence. The agent doesn't just surface the data — it interprets it, structures it, and escalates it."*

---

<br>

## 🎬 SCENARIO 05 — The MCP Demo (The Jaw-Dropper)

**Open Claude Desktop. Type: "Show me Sarah Mitchell's financial health and tell me if she qualifies for a mortgage."**

### What Happens
1. Claude calls `get_user_profile("USR-001")` → name, KYC, credit score, risk profile
2. Claude calls `get_financial_intelligence("USR-001")` → DTI ratio 22.4%, monthly debt load ₹18,200
3. Claude calls `get_loans("USR-001")` → existing personal loan + auto loan
4. Claude calls `get_portfolio("USR-001")` → ₹4.2L in equity holdings
5. Claude synthesizes all four data sources and responds:

> *"Sarah has a 742 credit score, a 22.4% DTI, and ₹4.2L in liquid assets. She is a strong candidate for a mortgage. I recommend offering a ₹35L loan at 5.5% given her income profile. Would you like me to file the application?"*

### Why This Is the Future
You didn't build a chatbot.  
You built a **banking API that any AI in the world can plug into.**  
Claude didn't hallucinate any numbers. It pulled **live data from Oracle 26ai** through a standardized protocol.  
This is what MCP is for. This is why it matters.

---

<br>

## 🎬 SCENARIO 06 — The Multi-Agent Chain

**"I'm travelling to Tokyo next week. I need ¥500,000 converted and transferred to my travel account, and I also want to make sure my card isn't blocked."**

### What Happens
The **LangGraph Supervisor** runs a **multi-hop cyclic execution**:

```
Hop 1 → Transaction Agent   (checks balance, calculates exchange rate ¥→₹, prepares transfer)
Hop 2 → Fraud Agent         (flags the international transaction pattern, verifies travel intent)
Hop 3 → Compliance Agent    (checks AML — large forex transaction near reporting threshold)
Hop 4 → FINISH              (Supervisor determines all checks pass, returns consolidated response)
```

Each agent adds its findings to the shared **AgentState context object**. The final response synthesises all three agents' outputs into one coherent message — exchange rate, transfer status, fraud clearance, card status.

### The Demo Moment
Show the **Multi-Agent Orchestration Log** in the chat UI as this runs. The audience can watch each agent "think" in real time — the Supervisor routing, the agents executing, the state updating. It looks like watching a team of analysts work.

---

<br>

## 🎬 SCENARIO 07 — The Episodic Memory Test

**First message**: *"I'm thinking about investing in green energy ETFs."*
*(Agent gives recommendations, mentions GREN ETF specifically)*

**Three messages later** — different topic entirely, then:  
**Second message**: *"Actually, let's go ahead with what you suggested earlier."*

### What Happens
The system doesn't ask *"What did I suggest?"*  
The **MemorySaver checkpointer** has persisted the entire `AgentState` for this session thread.  
The Supervisor detects a short continuity response, checks `session.lastAgent`, retrieves the context — and the Investment Agent picks up exactly where it left off, filing the GREN ETF trade.

### The Line That Lands
> *"This isn't a stateless API call. Every conversation has a persistent thread. The AI remembers what it said, what the user agreed to, and what's pending — across the entire session."*

---

<br>

## 🎬 SCENARIO 08 — The Banker Copilot

**Switch to the Banker Portal. Select a customer. Type: "Draft a risk summary for this client's loan renewal next week."**

### What Happens
The **Banker Copilot Agent** — a completely separate LangGraph-powered agent — pulls:
- Credit score trajectory
- Current DTI ratio and loan load
- Recent high-risk transactions
- KYC expiry status
- Portfolio net worth

It produces a formatted **Risk Summary Brief** ready to present in a meeting — with a recommendation on whether to renew, renegotiate rates, or request additional collateral.

### The Slide Caption
*"Your AI doesn't just serve customers. It makes your bankers 10x more effective."*

---

<br>

## 🎬 SCENARIO 09 — The Real-Time Dashboard

**Don't say anything. Just transfer ₹1,200 to an account and watch the dashboard.**

### What Happens
- The **account balance widget** updates *immediately* — no page refresh
- A new **transaction card** appears in the activity feed with a green `credit` / red `debit` chip
- The **spending chart** re-renders with the new data point
- If the Fraud Agent scores the transaction > 0.6, a **amber risk badge** appears on the transaction card automatically

All of this happens via **WebSockets**. The FastAPI server pushes events. The frontend listens. No polling. No refresh. Just live state.

### The Demo Moment
Do the transfer on one screen. Show the dashboard on another. The audience will watch the number change in real time. That's the moment.

---

<br>

## 🎬 SCENARIO 10 — The Architecture Conversation

**For technical audiences. Show the LangGraph graph diagram from the README.**

### What to Say

> "Most people building 'AI banking' are wrapping GPT in a chatbot and calling it a day.
>
> What we built is fundamentally different.
>
> Every message goes into a **typed state object** that flows through a **compiled StateGraph**. The Supervisor node evaluates that state after every agent execution and decides — dynamically, not from a lookup table — whether the task is done or if another specialist needs to step in.
>
> The state is checkpointed by **MemorySaver** after every hop. If a hop fails, it can be resumed from the last checkpoint. That's resilience.
>
> The Oracle 26ai database stores both the **relational schema** *and* the **1536-dimensional vector embeddings** for semantic memory — in the same database, no separate vector store needed.
>
> And then there's the **MCP Server** — a completely separate process that exposes every banking function as a structured tool. Any LLM in the world that speaks MCP can now autonomously interact with this system.
>
> This is what production-grade agentic AI infrastructure looks like."

---

<br>

## 📊 The Numbers Slide

| Metric | Value |
|---|---|
| **AI Agents in the Swarm** | 7 (Transaction, Fraud, Loan, Compliance, Investment, Customer Service, Banker Copilot) |
| **LangGraph Nodes** | 8 explicit nodes + Supervisor + Finalizer |
| **MCP Tools Exposed** | 19 across 6 categories |
| **Max Supervisor Hops** | 4 per request (with recursion safety) |
| **Vector Dimensions** | 1536-dim L2-normalized float32 embeddings in Oracle |
| **Human-in-the-Loop Gates** | Transfer > ₹10,000 · Trade > ₹5,000 · Account Freeze · KYC Flagged · All Loans |
| **WebSocket Event Types** | `agent:trace` · `transaction` · `approval:pending` · `agent:alert` · `account:updated` |
| **Database** | Oracle 26ai Free with native `VECTOR` column type |
| **Auth** | JWT + SHA-256 password hashing + OAuth2 SSO + RBAC middleware |
| **Lines of Python** | ~4,000 across 15 modules |

---

<br>

## 💡 The LinkedIn Caption Template

```
🏦 I built an autonomous AI banking system from scratch. Here's what happens 
when you type "I think someone hacked my account":

1. A LangGraph Supervisor evaluates your intent in real time
2. The Fraud Agent scans 50 transactions for anomaly patterns
3. Structuring is detected (3 transactions just below ₹5L threshold)
4. A CRITICAL alert fires to the Banker Dashboard over WebSocket
5. The banker is notified — before you finish reading the AI's response

No keyword rules. No decision trees. Pure agentic reasoning.

Built with: Python · FastAPI · LangGraph · Oracle 26ai · MCP

The era of AI-first banking infrastructure is here.
What questions do you have? 👇

#AI #LangGraph #Banking #Fintech #MultiAgent #MCP #Oracle #Python
```

---

<br>

## 🎯 The One Sentence That Closes Every Demo

> *"This isn't a chatbot with a banking skin. This is a multi-agent AI system where the LLM is the orchestrator, not the interface — and the human is still in control of every decision that matters."*

---

*Built with AgenticBank AI — AgenticBank AI Autonomous Banking Command Center*  
*Stack: Python 3.14 · FastAPI · LangGraph 0.2 · LangChain · Oracle 26ai Free · MCP 1.27 · Vanilla JS · WebSockets*
