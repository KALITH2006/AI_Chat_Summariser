const API_URL = 'http://localhost:8000';

const transcriptInput = document.getElementById('transcript');
const wordCountEl = document.getElementById('word-count');
const charCountEl = document.getElementById('char-count');
const loadingEl = document.getElementById('loading');
const btnSummarise = document.getElementById('btn-summarise');
const metricsPanel = document.getElementById('metrics-panel');
const emotionBreakdownSection = document.getElementById('emotion-breakdown-section');

// Format
transcriptInput.addEventListener('input', () => {
    const text = transcriptInput.value;
    charCountEl.textContent = `${text.length} chars`;
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;
    wordCountEl.textContent = `${words} words`;
});

document.getElementById('btn-clear').addEventListener('click', () => {
    transcriptInput.value = '';
    transcriptInput.dispatchEvent(new Event('input'));
});

document.getElementById('btn-paste-sample').addEventListener('click', () => {
    transcriptInput.value = "User: I'm really frustrated with how this API is structured. It keeps failing and the docs are terrible.\nBot: I understand that can be very annoying. Let's look at the error logs together to figure out where it's breaking.\nUser: Ah, I see the issue now. I was missing the authentication header. That's a huge relief, it works perfectly now! Thanks!";
    transcriptInput.dispatchEvent(new Event('input'));
});

// Tabs
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
        
        btn.classList.add('active');
        document.getElementById(`tab-${btn.dataset.tab}`).classList.remove('hidden');
        
        if (btn.dataset.tab === 'history') {
            fetchHistory();
        }
    });
});

// Summarise
btnSummarise.addEventListener('click', async () => {
    const transcript = transcriptInput.value.trim();
    if (!transcript) {
        alert("Please paste a transcript first.");
        return;
    }

    const method = document.getElementById('config-method').value;
    const length = document.getElementById('config-length').value;
    const tone = document.getElementById('config-tone').value;

    loadingEl.classList.remove('hidden');
    btnSummarise.disabled = true;

    try {
        const response = await fetch(`${API_URL}/summarise`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transcript, method, length, tone })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Summarisation failed');
        }

        const data = await response.json();
        displayResults(data);
        
        // switch tab
        document.querySelector('[data-tab="results"]').click();
    } catch (error) {
        alert("Error: " + error.message);
    } finally {
        loadingEl.classList.add('hidden');
        btnSummarise.disabled = false;
    }
});

function displayResults(data) {
    metricsPanel.classList.remove('hidden');
    
    // Emotion parsing
    if (data.emotions && data.emotions.dominant_emotion) {
        document.getElementById('res-emotion').textContent = data.emotions.dominant_emotion;
        document.getElementById('res-emotion-conf').textContent = `Confidence: ${(data.emotions.confidence * 100).toFixed(1)}%`;
        
        if (data.emotions.top_emotions && data.emotions.top_emotions.length > 0) {
            emotionBreakdownSection.classList.remove('hidden');
            const emotionHtml = data.emotions.top_emotions.map(em => 
                `<span class="tag" style="background:#fdf2f8;color:#be185d;">${em.label} (${(em.score*100).toFixed(0)}%)</span>`
            ).join('');
            document.getElementById('res-top-emotions').innerHTML = emotionHtml;
        } else {
            emotionBreakdownSection.classList.add('hidden');
        }
    } else {
        document.getElementById('res-emotion').textContent = '-';
        document.getElementById('res-emotion-conf').textContent = '';
        emotionBreakdownSection.classList.add('hidden');
    }

    document.getElementById('res-compression').textContent = data.compressionRatio || '-';
    document.getElementById('res-turns').textContent = data.turnCount || '-';
    
    document.getElementById('res-summary').textContent = data.summary;
    
    const topicsHtml = (data.topics || []).map(t => `<span class="tag topic-tag">${t}</span>`).join('');
    document.getElementById('res-topics').innerHTML = topicsHtml;
    
    const keywordsHtml = (data.keywords || []).map(k => `<span class="tag">${k}</span>`).join('');
    document.getElementById('res-keywords').innerHTML = keywordsHtml;
    
    const stepsHtml = (data.nextSteps || []).map(s => `<li>${s}</li>`).join('');
    document.getElementById('res-nextsteps').innerHTML = stepsHtml;

    if (data.passport) {
        document.getElementById('passport-code').value = data.passport;
    }

    if (data.resumePrompt) {
        document.getElementById('resume-prompt-section').classList.remove('hidden');
        document.getElementById('res-prompt').textContent = data.resumePrompt;
    }
}

// Passport Actions
document.getElementById('btn-copy-passport').addEventListener('click', () => {
    const passportCode = document.getElementById('passport-code');
    passportCode.select();
    document.execCommand('copy');
    alert('Passport copied to clipboard!');
});

document.getElementById('btn-download-passport').addEventListener('click', () => {
    const passportCode = document.getElementById('passport-code').value;
    if (!passportCode) {
        alert("No passport available to download.");
        return;
    }
    const blob = new Blob([passportCode], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `session-passport-${new Date().getTime()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
});

document.getElementById('btn-decode-passport').addEventListener('click', async () => {
    const passportCode = document.getElementById('passport-code').value.trim();
    if (!passportCode) {
        alert("Paste a passport string first.");
        return;
    }

    try {
        const response = await fetch(`${API_URL}/passport/decode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ passport: passportCode })
        });
        
        if (!response.ok) {
            throw new Error("Invalid passport code.");
        }

        const data = await response.json();
        
        displayResults({
            ...data,
            compressionRatio: 'N/A',
            turnCount: 'N/A'
        });
        
        alert("Passport decoded successfully!");
        document.querySelector('[data-tab="results"]').click();
        
    } catch (error) {
        alert(error.message);
    }
});

document.getElementById('btn-copy-prompt').addEventListener('click', () => {
    const promptText = document.getElementById('res-prompt').textContent;
    navigator.clipboard.writeText(promptText);
    alert('Resume prompt copied!');
});

// History
document.getElementById('btn-refresh-history').addEventListener('click', fetchHistory);

async function fetchHistory() {
    const historyList = document.getElementById('history-list');
    historyList.innerHTML = 'Loading...';
    try {
        const response = await fetch(`${API_URL}/history`);
        if (!response.ok) throw new Error("Failed to load history");
        
        const data = await response.json();
        if (data.history.length === 0) {
            historyList.innerHTML = 'No sessions found.';
            return;
        }
        
        historyList.innerHTML = data.history.map(item => `
            <div class="history-item" data-passport="${item.passport}">
                <strong>${new Date(item.created_at).toLocaleString()}</strong>
                <p>${item.summary.substring(0, 100)}...</p>
            </div>
        `).join('');

        document.querySelectorAll('.history-item').forEach(el => {
            el.addEventListener('click', () => {
                document.getElementById('passport-code').value = el.dataset.passport;
                document.getElementById('btn-decode-passport').click();
            });
        });

    } catch (error) {
        historyList.innerHTML = `<p style="color:red">${error.message}</p>`;
    }
}
