const fs = require('fs');

let content = fs.readFileSync('src/data/seedData.js', 'utf-8');

// Match properties and scale their values
const propsToScale = [
    'annualIncome', 'balance', 'creditLimit', 'amount', 'remainingBalance', 
    'monthlyPayment', 'totalValue', 'avgCost', 'currentPrice'
];

propsToScale.forEach(prop => {
    // Regex matches prop: 1234.56
    const regex = new RegExp(`(${prop}\\s*:\\s*)([0-9.]+)`, 'g');
    content = content.replace(regex, (match, p1, p2) => {
        return `${p1}${parseFloat(p2) * 80}`;
    });
});

// Also scale the txnTemplates ranges
content = content.replace(/(range\s*:\s*\[)([0-9.]+)(,\s*)([0-9.]+)(\])/g, (match, p1, p2, p3, p4, p5) => {
    return `${p1}${parseFloat(p2) * 80}${p3}${parseFloat(p4) * 80}${p5}`;
});

// Also format amounts to 2 decimals if they have decimals
content = content.replace(/([0-9]+\.[0-9]{3,})/g, (match) => {
    return parseFloat(match).toFixed(2);
});

// Change USD to INR
content = content.replace(/currency: 'USD'/g, "currency: 'INR'");

fs.writeFileSync('src/data/seedData.js', content, 'utf-8');
console.log('Scaled seed data by 80');
