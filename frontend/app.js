const API_URL = 'https://research-bookmarks-api.onrender.com';

const searchForm = document.getElementById('search-form');
const searchInput = document.getElementById('search-input');
const showAllBtn = document.getElementById('show-all-btn');
const addForm = document.getElementById('add-form');
const urlInput = document.getElementById('url-input');
const addStatus = document.getElementById('add-status');
const toggleManualBtn = document.getElementById('toggle-manual');
const manualForm = document.getElementById('manual-form');
const manualUrl = document.getElementById('manual-url');
const manualTitle = document.getElementById('manual-title');
const manualContent = document.getElementById('manual-content');
const resultsHeading = document.getElementById('results-heading');
const resultsContainer = document.getElementById('results');
const resultsSection = document.querySelector('.results-section');
const loadingEl = document.getElementById('loading');
const errorEl = document.getElementById('error');

// Synthesis elements
const synthesisBar = document.getElementById('synthesis-bar');
const selectedCountEl = document.getElementById('selected-count');
const focusTopicInput = document.getElementById('focus-topic');
const synthesizeBtn = document.getElementById('synthesize-btn');
const clearSelectionBtn = document.getElementById('clear-selection');
const synthesisModal = document.getElementById('synthesis-modal');
const synthesisResult = document.getElementById('synthesis-result');
const closeModalBtn = document.getElementById('close-modal');

// Export elements
const copyClipboardBtn = document.getElementById('copy-clipboard-btn');
const downloadBtn = document.getElementById('download-btn');
const toast = document.getElementById('toast');

// Track selected articles
let selectedArticles = new Map(); // id -> article data
let isSearchMode = false;

// Toast notification
function showToast(message, type = 'success') {
    toast.textContent = message;
    toast.className = `toast ${type}`;

    // Force reflow to restart animation
    void toast.offsetWidth;

    toast.classList.add('visible');

    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 300);
    }, 3000);
}

// Fetch full article data for export (includes clean_text)
async function fetchFullArticles() {
    const articleIds = Array.from(selectedArticles.keys());
    if (articleIds.length === 0) return [];

    try {
        const response = await fetch(`${API_URL}/articles/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(articleIds)
        });

        if (!response.ok) throw new Error('Failed to fetch articles');
        return await response.json();
    } catch (err) {
        console.error('Export fetch failed:', err);
        // Fall back to cached data (without full text)
        return Array.from(selectedArticles.values());
    }
}

// Format articles for export
function formatArticlesForExport(articles) {
    let output = '';

    articles.forEach((article, index) => {
        output += `${'='.repeat(80)}\n`;
        output += `ARTICLE ${index + 1}: ${article.title || 'Untitled'}\n`;
        output += `${'='.repeat(80)}\n\n`;
        output += `URL: ${article.url}\n`;
        output += `Domain: ${article.domain || 'Unknown'}\n`;
        output += `Date Saved: ${new Date(article.created_at).toLocaleDateString()}\n\n`;
        output += `SUMMARY:\n${article.summary || 'No summary available'}\n\n`;

        // Include full article text for NotebookLM
        if (article.clean_text) {
            output += `FULL TEXT:\n${article.clean_text}\n\n`;
        }

        output += `${'─'.repeat(80)}\n\n`;
    });

    output += `\nExported from Research Bookmarks on ${new Date().toLocaleDateString()}\n`;
    output += `Total articles: ${articles.length}\n`;

    return output;
}

// Copy to clipboard
async function copyToClipboard() {
    if (selectedArticles.size === 0) {
        showToast('No articles selected', 'error');
        return;
    }

    showToast('Fetching full article text...', 'success');
    const articles = await fetchFullArticles();
    const text = formatArticlesForExport(articles);

    try {
        await navigator.clipboard.writeText(text);
        showToast(`${articles.length} article${articles.length > 1 ? 's' : ''} with full text copied!`, 'success');
    } catch (err) {
        showToast('Failed to copy to clipboard', 'error');
    }
}

// Download as file
async function downloadAsFile() {
    if (selectedArticles.size === 0) {
        showToast('No articles selected', 'error');
        return;
    }

    showToast('Fetching full article text...', 'success');
    const articles = await fetchFullArticles();
    const text = formatArticlesForExport(articles);
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `research-articles-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast(`${articles.length} article${articles.length > 1 ? 's' : ''} with full text downloaded!`, 'success');
}

function showLoading() {
    loadingEl.classList.remove('hidden');
    errorEl.classList.add('hidden');
    resultsContainer.innerHTML = '';
}

function hideLoading() {
    loadingEl.classList.add('hidden');
}

function showError(message) {
    errorEl.textContent = message;
    errorEl.classList.remove('hidden');
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function updateSynthesisBar() {
    const count = selectedArticles.size;
    if (count > 0 && isSearchMode) {
        synthesisBar.classList.add('visible');
        synthesisBar.classList.remove('hidden');
        document.body.classList.add('synthesis-active');
        selectedCountEl.textContent = `${count} article${count > 1 ? 's' : ''} selected`;
    } else {
        synthesisBar.classList.remove('visible');
        document.body.classList.remove('synthesis-active');
    }
}

function toggleArticleSelection(article, checkbox, card) {
    if (selectedArticles.has(article.id)) {
        selectedArticles.delete(article.id);
        checkbox.checked = false;
        card.classList.remove('selected');
    } else {
        selectedArticles.set(article.id, article);
        checkbox.checked = true;
        card.classList.add('selected');
    }
    updateSynthesisBar();
}

function renderArticle(article, showSimilarity = false) {
    const card = document.createElement('div');
    card.className = 'article-card';
    if (selectedArticles.has(article.id)) {
        card.classList.add('selected');
    }

    const title = article.title || 'Untitled';
    const summary = article.summary || 'No summary available';
    const domain = article.domain || new URL(article.url).hostname;

    let metaHtml = `
        <span class="domain">${domain}</span>
        <span class="date">${formatDate(article.created_at)}</span>
    `;

    let relevanceHtml = '';
    if (showSimilarity && article.similarity !== undefined) {
        const percent = (article.similarity * 100).toFixed(0);
        relevanceHtml = `
            <div class="relevance-bar">
                <div class="relevance-bar-label">
                    <span>Relevance</span>
                    <span>${percent}%</span>
                </div>
                <div class="relevance-bar-track">
                    <div class="relevance-bar-fill" style="width: ${percent}%"></div>
                </div>
            </div>
        `;
    }

    // Add checkbox for search results
    let checkboxHtml = '';
    if (showSimilarity) {
        const checked = selectedArticles.has(article.id) ? 'checked' : '';
        checkboxHtml = `<input type="checkbox" class="select-checkbox" ${checked}>`;
    }

    card.innerHTML = `
        <div class="card-header">
            ${checkboxHtml}
            <div class="card-content">
                <h3><a href="${article.url}" target="_blank">${title}</a></h3>
                <p class="summary">${summary}</p>
                <div class="meta">${metaHtml}</div>
                ${relevanceHtml}
            </div>
        </div>
    `;

    // Add click handler for checkbox
    if (showSimilarity) {
        const checkbox = card.querySelector('.select-checkbox');
        checkbox.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleArticleSelection(article, checkbox, card);
        });

        // Also allow clicking the card to select
        card.addEventListener('click', (e) => {
            if (e.target.tagName !== 'A' && e.target.tagName !== 'INPUT') {
                toggleArticleSelection(article, checkbox, card);
            }
        });
    }

    return card;
}

function renderArticles(articles, isSearch = false) {
    resultsContainer.innerHTML = '';

    if (articles.length === 0) {
        resultsContainer.innerHTML = `
            <div class="empty-state">
                ${isSearch ? 'No matching articles found.' : 'No articles saved yet. Add your first article above!'}
            </div>
        `;
        return;
    }

    articles.forEach(article => {
        resultsContainer.appendChild(renderArticle(article, isSearch));
    });
}

async function loadAllArticles() {
    showLoading();
    loadingEl.innerHTML = 'Loading articles<br><small style="color: #888;">(first load may take ~30s while server wakes up)</small>';
    resultsHeading.textContent = 'Recent Articles';
    resultsSection.classList.remove('search-mode');
    isSearchMode = false;
    selectedArticles.clear();
    updateSynthesisBar();

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s timeout

        const response = await fetch(`${API_URL}/articles`, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (!response.ok) throw new Error('Failed to load articles');

        const articles = await response.json();
        renderArticles(articles, false);
    } catch (err) {
        if (err.name === 'AbortError') {
            showError('Request timed out. The server may be starting up - please try again in a moment.');
        } else {
            showError('Failed to load articles. Please refresh to try again.');
        }
    } finally {
        loadingEl.textContent = 'Loading...';
        hideLoading();
    }
}

async function searchArticles(query) {
    showLoading();
    resultsHeading.textContent = `Search Results for "${query}"`;
    resultsSection.classList.add('search-mode');
    isSearchMode = true;
    selectedArticles.clear();
    updateSynthesisBar();

    try {
        const response = await fetch(`${API_URL}/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, limit: 20 })
        });

        if (!response.ok) throw new Error('Search failed');

        const results = await response.json();
        renderArticles(results, true);
    } catch (err) {
        showError('Search failed. Please try again.');
    } finally {
        hideLoading();
    }
}

async function addArticle(url) {
    addStatus.className = 'status';
    addStatus.style.display = 'none';

    const submitBtn = addForm.querySelector('button');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving...';

    try {
        const response = await fetch(`${API_URL}/articles`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const data = await response.json();

        if (response.status === 409) {
            addStatus.className = 'status error';
            addStatus.textContent = 'This article has already been saved.';
            addStatus.style.display = 'block';
            return;
        }

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to save article');
        }

        addStatus.className = 'status success';
        addStatus.textContent = `Saved: "${data.title || 'Article'}"`;
        addStatus.style.display = 'block';
        urlInput.value = '';

        loadAllArticles();

    } catch (err) {
        addStatus.className = 'status error';
        addStatus.textContent = err.message || 'Failed to save article';
        addStatus.style.display = 'block';
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save Article';
    }
}

// Synthesis functions
async function synthesizeSelected() {
    const focusTopic = focusTopicInput.value.trim();
    if (!focusTopic) {
        focusTopicInput.focus();
        focusTopicInput.style.borderColor = '#ff4444';
        setTimeout(() => focusTopicInput.style.borderColor = '', 2000);
        return;
    }

    const articleIds = Array.from(selectedArticles.keys());
    if (articleIds.length === 0) return;

    // Show modal with loading
    synthesisModal.classList.remove('hidden');
    synthesisResult.innerHTML = '<div class="synthesis-loading">Synthesizing your research...</div>';

    synthesizeBtn.disabled = true;
    synthesizeBtn.textContent = 'Synthesizing...';

    try {
        const response = await fetch(`${API_URL}/synthesize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                article_ids: articleIds,
                focus_topic: focusTopic
            })
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Synthesis failed');
        }

        const data = await response.json();

        // Convert markdown to HTML (basic conversion)
        let html = data.summary
            .replace(/^## (.*$)/gm, '<h2>$1</h2>')
            .replace(/^### (.*$)/gm, '<h3>$1</h3>')
            .replace(/^\* (.*$)/gm, '<li>$1</li>')
            .replace(/^- (.*$)/gm, '<li>$1</li>')
            .replace(/^> (.*$)/gm, '<blockquote>$1</blockquote>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/(<li>.*<\/li>)\n(?=<li>)/g, '$1');

        // Wrap lists
        html = html.replace(/(<li>.*?<\/li>)+/gs, '<ul>$&</ul>');

        // Clean up consecutive blockquotes
        html = html.replace(/<\/blockquote>\s*<blockquote>/g, '<br>');

        synthesisResult.innerHTML = `<p>${html}</p>`;

    } catch (err) {
        synthesisResult.innerHTML = `<div class="error">${err.message || 'Failed to synthesize articles'}</div>`;
    } finally {
        synthesizeBtn.disabled = false;
        synthesizeBtn.textContent = 'Synthesize';
    }
}

function closeModal() {
    synthesisModal.classList.add('hidden');
}

function clearSelection() {
    selectedArticles.clear();
    document.querySelectorAll('.article-card.selected').forEach(card => {
        card.classList.remove('selected');
        const checkbox = card.querySelector('.select-checkbox');
        if (checkbox) checkbox.checked = false;
    });
    updateSynthesisBar();
}

// Event listeners
searchForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const query = searchInput.value.trim();
    if (query) {
        searchArticles(query);
    }
});

showAllBtn.addEventListener('click', () => {
    searchInput.value = '';
    loadAllArticles();
});

addForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (url) {
        addArticle(url);
    }
});

// Toggle manual entry form
toggleManualBtn.addEventListener('click', () => {
    const isHidden = manualForm.classList.contains('hidden');
    if (isHidden) {
        manualForm.classList.remove('hidden');
        addForm.classList.add('hidden');
        toggleManualBtn.classList.add('active');
        toggleManualBtn.textContent = 'Auto Extract';
    } else {
        manualForm.classList.add('hidden');
        addForm.classList.remove('hidden');
        toggleManualBtn.classList.remove('active');
        toggleManualBtn.textContent = 'Manual Entry';
    }
});

// Manual form submission
async function addManualArticle(url, title, content) {
    addStatus.className = 'status';
    addStatus.style.display = 'none';

    const submitBtn = manualForm.querySelector('button');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving...';

    try {
        const response = await fetch(`${API_URL}/articles/manual`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, title, content })
        });

        const data = await response.json();

        if (response.status === 409) {
            addStatus.className = 'status error';
            addStatus.textContent = 'This article has already been saved.';
            addStatus.style.display = 'block';
            return;
        }

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to save article');
        }

        addStatus.className = 'status success';
        addStatus.textContent = `Saved: "${data.title || 'Article'}"`;
        addStatus.style.display = 'block';
        manualUrl.value = '';
        manualTitle.value = '';
        manualContent.value = '';

        loadAllArticles();

    } catch (err) {
        addStatus.className = 'status error';
        addStatus.textContent = err.message || 'Failed to save article';
        addStatus.style.display = 'block';
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save Manual Entry';
    }
}

manualForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const url = manualUrl.value.trim();
    const title = manualTitle.value.trim();
    const content = manualContent.value.trim();
    if (url && title && content) {
        addManualArticle(url, title, content);
    }
});

// Synthesis event listeners
synthesizeBtn.addEventListener('click', synthesizeSelected);
clearSelectionBtn.addEventListener('click', clearSelection);
closeModalBtn.addEventListener('click', closeModal);
synthesisModal.addEventListener('click', (e) => {
    if (e.target === synthesisModal) closeModal();
});

// Export event listeners
copyClipboardBtn.addEventListener('click', copyToClipboard);
downloadBtn.addEventListener('click', downloadAsFile);

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !synthesisModal.classList.contains('hidden')) {
        closeModal();
    }
});

// Tab navigation
const tabBtns = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const targetTab = btn.dataset.tab;

        // Update button states
        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Update content visibility
        tabContents.forEach(content => {
            content.classList.remove('active');
            if (content.id === `${targetTab}-tab`) {
                content.classList.add('active');
            }
        });
    });
});

loadAllArticles();
