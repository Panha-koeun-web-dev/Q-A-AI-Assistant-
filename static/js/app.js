    const savedTheme = localStorage.getItem('qa_ai_theme') || 'dark';

    const state = {
      user: null,
      token: localStorage.getItem('qa_ai_token') || '',
      currentConversationId: null,
      conversations: [],
      history: [],
      attachments: [],
      isGenerating: false,
      model: localStorage.getItem('qa_ai_model') || 'gemini-3.5-flash',
      systemInstructions: `You are QA AI Assistant, built by Panha Koeun.
- Your name is QA AI Assistant.
- You were built and developed by Panha Koeun.
- If asked who you are, what your name is, or who created you, always introduce yourself as QA AI Assistant built by Panha Koeun. Never call yourself ChatGPT or claim to be built by OpenAI.
- Answer questions directly, clearly, and thoroughly.
- Format code blocks using appropriate syntax identifiers.
- Explain concepts with helpful step-by-step examples when relevant.
- Remember and respect user preferences, profile details, and memories.
- Be polite, professional, and helpful.`,
      theme: savedTheme,
      authMode: 'login'
    };

    const chatContainer = document.getElementById('chat-container');
    const emptyState = document.getElementById('empty-state');
    const inputEl = document.getElementById('question-input');
    const sendBtn = document.getElementById('send-btn');
    const attachBtn = document.getElementById('attach-btn');
    const fileInput = document.getElementById('file-input');
    const attachmentPreview = document.getElementById('attachment-preview');
    const dropZone = document.getElementById('drop-zone');
    const themeBtn = document.getElementById('theme-btn');
    const settingsBtn = document.getElementById('settings-btn');
    const settingsModal = document.getElementById('settings-modal');
    const authModal = document.getElementById('auth-modal');
    const memoryModal = document.getElementById('memory-modal');
    const memoryBtn = document.getElementById('memory-btn');
    const newChatBtn = document.getElementById('new-chat-btn');
    const historyList = document.getElementById('history-list');
    const authSection = document.getElementById('auth-section');
    const sidebar = document.getElementById('sidebar');
    const sidebarFooter = document.getElementById('sidebar-footer');
    const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
    const sidebarBackdrop = document.getElementById('sidebar-backdrop');

    // Restore sidebar desktop collapsed state
    if (window.innerWidth > 768 && localStorage.getItem('qa_ai_sidebar_collapsed') === 'true') {
      sidebar.classList.add('collapsed');
    }

    function toggleSidebar() {
      if (window.innerWidth <= 768) {
        const isOpen = sidebar.classList.toggle('open');
        if (sidebarBackdrop) sidebarBackdrop.classList.toggle('active', isOpen);
      } else {
        const isCollapsed = sidebar.classList.toggle('collapsed');
        localStorage.setItem('qa_ai_sidebar_collapsed', isCollapsed);
      }
    }

    function closeSidebarMobile() {
      if (window.innerWidth <= 768) {
        sidebar.classList.remove('open');
        if (sidebarBackdrop) sidebarBackdrop.classList.remove('active');
      }
    }

    // Theme initialization
    document.documentElement.setAttribute('data-theme', state.theme);
    themeBtn.textContent = state.theme === 'dark' ? '🌙' : '☀️';

    marked.setOptions({
      highlight: function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
          return hljs.highlight(code, { language: lang }).value;
        }
        return hljs.highlightAuto(code).value;
      },
      breaks: true
    });

    // Event Listeners
    inputEl.addEventListener('input', () => {
      inputEl.style.height = 'auto';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
    });

    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitQuestion();
      }
    });

    sendBtn.addEventListener('click', submitQuestion);
    settingsBtn.addEventListener('click', openSettingsModal);
    newChatBtn.addEventListener('click', startNewChat);
    if (memoryBtn) memoryBtn.addEventListener('click', openMemoryModal);
    toggleSidebarBtn.addEventListener('click', toggleSidebar);
    if (sidebarBackdrop) {
      sidebarBackdrop.addEventListener('click', closeSidebarMobile);
    }

    // File Attachment Event Listeners
    if (attachBtn && fileInput) {
      attachBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileInput.click();
      });
      fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
          handleFiles(e.target.files);
          fileInput.value = '';
        }
      });
    }

    // Global Drag and Drop & Paste
    window.addEventListener('dragover', (e) => {
      e.preventDefault();
      if (dropZone) dropZone.classList.add('dragover');
    });

    window.addEventListener('dragleave', (e) => {
      if (e.clientX <= 0 || e.clientY <= 0) {
        if (dropZone) dropZone.classList.remove('dragover');
      }
    });

    window.addEventListener('drop', (e) => {
      e.preventDefault();
      if (dropZone) dropZone.classList.remove('dragover');
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFiles(e.dataTransfer.files);
      }
    });

    inputEl.addEventListener('paste', (e) => {
      const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items;
      if (!items) return;
      const files = [];
      for (const item of items) {
        if (item.kind === 'file') {
          const file = item.getAsFile();
          if (file) files.push(file);
        }
      }
      if (files.length > 0) {
        handleFiles(files);
      }
    });

    themeBtn.addEventListener('click', () => {
      state.theme = state.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', state.theme);
      themeBtn.textContent = state.theme === 'dark' ? '🌙' : '☀️';
      localStorage.setItem('qa_ai_theme', state.theme);
    });

    // =========================================================================
    // Attachment Handling Logic
    // =========================================================================
    const MAX_ATTACHMENTS = 4;
    const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

    function formatFileSize(bytes) {
      if (bytes < 1024) return bytes + ' B';
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
      return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    async function handleFiles(fileList) {
      const files = Array.from(fileList);
      for (const file of files) {
        if (state.attachments.length >= MAX_ATTACHMENTS) {
          alert(`You can attach a maximum of ${MAX_ATTACHMENTS} files per message.`);
          break;
        }

        if (file.size > MAX_FILE_SIZE) {
          alert(`File "${file.name}" exceeds the 10 MB size limit.`);
          continue;
        }

        const ext = file.name.includes('.') ? file.name.split('.').pop().toLowerCase() : '';
        const isImage = (file.type && file.type.startsWith('image/')) || ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'].includes(ext);
        const binaryDocExtensions = ['pdf', 'docx', 'doc', 'xlsx', 'xls', 'pptx', 'ppt'];
        const textExtensions = ['txt', 'py', 'js', 'html', 'css', 'json', 'md', 'csv', 'tsv', 'sql', 'xml', 'yaml', 'yml', 'sh', 'ts', 'jsx', 'tsx', 'php', 'c', 'cpp', 'h', 'java', 'go', 'rs', 'log', 'env'];

        let fileIcon = '📄';
        if (ext === 'pdf') fileIcon = '📕';
        else if (['doc', 'docx'].includes(ext)) fileIcon = '📘';
        else if (['xls', 'xlsx', 'csv'].includes(ext)) fileIcon = '📊';
        else if (['py', 'js', 'ts', 'html', 'css', 'json', 'sql', 'php', 'java', 'cpp'].includes(ext)) fileIcon = '💻';

        if (isImage) {
          try {
            const dataUrl = await readFileAsDataURL(file);
            const base64Data = dataUrl.split(',')[1];
            state.attachments.push({
              name: file.name,
              type: file.type || 'image/jpeg',
              size: file.size,
              data: base64Data,
              text: null,
              previewUrl: dataUrl,
              isImage: true,
              icon: '🖼️'
            });
          } catch (err) {
            console.error('Failed to read image:', err);
          }
        } else if (binaryDocExtensions.includes(ext) || file.type.includes('pdf') || file.type.includes('document') || file.type.includes('sheet')) {
          // Documents (PDF, Word, Excel) — read as base64 for backend document_service extraction
          try {
            const dataUrl = await readFileAsDataURL(file);
            const base64Data = dataUrl.split(',')[1];
            state.attachments.push({
              name: file.name,
              type: file.type || 'application/octet-stream',
              size: file.size,
              data: base64Data,
              text: null,
              previewUrl: null,
              isImage: false,
              icon: fileIcon
            });
          } catch (err) {
            console.error('Failed to read document:', err);
          }
        } else {
          // Text, code, config files
          try {
            const textContent = await readFileAsText(file);
            state.attachments.push({
              name: file.name,
              type: file.type || 'text/plain',
              size: file.size,
              data: null,
              text: textContent,
              previewUrl: null,
              isImage: false,
              icon: fileIcon
            });
          } catch (err) {
            console.error('Failed to read file:', err);
          }
        }
      }
      renderAttachmentPreviews();
    }

    function readFileAsDataURL(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    }

    function readFileAsText(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsText(file);
      });
    }

    function removeAttachment(index) {
      state.attachments.splice(index, 1);
      renderAttachmentPreviews();
    }
    window.removeAttachment = removeAttachment;

    function renderAttachmentPreviews() {
      if (!attachmentPreview) return;
      if (state.attachments.length === 0) {
        attachmentPreview.style.display = 'none';
        attachmentPreview.innerHTML = '';
        inputEl.placeholder = 'Ask Q&A AI any question or add files/images... (Press Enter to submit)';
        return;
      }

      attachmentPreview.style.display = 'flex';
      attachmentPreview.innerHTML = '';
      inputEl.placeholder = `📎 ${state.attachments.length} file(s) attached: type your question or press Enter...`;

      state.attachments.forEach((att, idx) => {
        const item = document.createElement('div');
        item.className = 'attachment-item';

        if (att.isImage && att.previewUrl) {
          item.classList.add('attachment-item-img');
          item.innerHTML = `
            <img src="${att.previewUrl}" alt="${att.name}" title="${att.name} (${formatFileSize(att.size)})">
            <button type="button" class="remove-btn" title="Remove" onclick="removeAttachment(${idx})">✕</button>
          `;
        } else {
          item.innerHTML = `
            <span>${att.icon || '📄'}</span>
            <span class="attachment-file-name" title="${att.name}">${att.name}</span>
            <span class="attachment-file-size">${formatFileSize(att.size)}</span>
            <button type="button" class="remove-btn" title="Remove" onclick="removeAttachment(${idx})">✕</button>
          `;
        }
        attachmentPreview.appendChild(item);
      });
    }

    // Authentication Logic
    async function checkAuth() {
      if (!state.token) {
        renderLoggedOut();
        return;
      }
      try {
        const res = await fetch('/api/auth/me', {
          headers: { 'Authorization': `Bearer ${state.token}` }
        });
        const data = await res.json();
        if (data.success && data.user) {
          state.user = data.user;
          renderLoggedIn();
          loadConversations();
          loadMemoriesCount();
        } else {
          localStorage.removeItem('qa_ai_token');
          state.token = '';
          renderLoggedOut();
        }
      } catch (err) {
        renderLoggedOut();
      }
    }

    function renderLoggedIn() {
      authSection.innerHTML = `
        <div class="user-pill" title="Logged in as ${state.user.username}">
          <div class="user-avatar-small">${state.user.username.charAt(0).toUpperCase()}</div>
          <span>${state.user.username}</span>
        </div>
      `;
      if (sidebarFooter) sidebarFooter.style.display = 'block';
      document.getElementById('welcome-sub').textContent = `Welcome back, ${state.user.username}! Ask any question to continue.`;
    }

    function renderLoggedOut() {
      state.user = null;
      authSection.innerHTML = `
        <button class="btn-icon" onclick="openAuthModal('login')">
          <span>👤</span>
          <span>Log In</span>
        </button>
      `;
      if (sidebarFooter) sidebarFooter.style.display = 'none';
      historyList.innerHTML = `<div style="padding:14px; font-size:0.8rem; color:var(--text-muted); text-align:center;">Log in to view and save conversation history.</div>`;
    }

    function openAuthModal(mode = 'login') {
      switchAuthTab(mode);
      authModal.classList.add('active');
    }

    function closeAuthModal() {
      authModal.classList.remove('active');
    }

    function switchAuthTab(mode) {
      state.authMode = mode;
      const isLogin = mode === 'login';
      document.getElementById('tab-login').classList.toggle('active', isLogin);
      document.getElementById('tab-signup').classList.toggle('active', !isLogin);
      document.getElementById('group-email').style.display = isLogin ? 'none' : 'block';
      document.getElementById('auth-submit-btn').textContent = isLogin ? 'Log In' : 'Create Account';
      document.getElementById('auth-error-msg').style.display = 'none';
    }

    async function submitAuth() {
      const username = document.getElementById('auth-username').value.trim();
      const password = document.getElementById('auth-password').value.trim();
      const email = document.getElementById('auth-email').value.trim();
      const errorEl = document.getElementById('auth-error-msg');

      if (!username || !password) {
        errorEl.textContent = 'Please fill in both username and password.';
        errorEl.style.display = 'block';
        return;
      }

      const endpoint = state.authMode === 'login' ? '/api/auth/login' : '/api/auth/register';

      try {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password, email })
        });
        const data = await res.json();
        if (data.success) {
          state.token = data.token;
          state.user = data.user;
          localStorage.setItem('qa_ai_token', data.token);
          closeAuthModal();
          renderLoggedIn();
          loadConversations();
          loadMemoriesCount();
        } else {
          errorEl.textContent = data.error || 'Authentication failed.';
          errorEl.style.display = 'block';
        }
      } catch (e) {
        errorEl.textContent = 'Network error contacting server.';
        errorEl.style.display = 'block';
      }
    }

    async function logout() {
      if (state.token) {
        fetch('/api/auth/logout', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${state.token}` }
        });
      }
      localStorage.removeItem('qa_ai_token');
      state.token = '';
      state.user = null;
      renderLoggedOut();
      startNewChat();
    }

    // Conversations / History Logic
    async function loadConversations() {
      if (!state.token) return;
      try {
        const res = await fetch('/api/conversations', {
          headers: { 'Authorization': `Bearer ${state.token}` }
        });
        const data = await res.json();
        if (data.success) {
          state.conversations = data.conversations;
          renderHistoryList();
        }
      } catch (err) {}
    }

    function renderHistoryList() {
      historyList.innerHTML = '';
      if (!state.conversations.length) {
        historyList.innerHTML = `<div style="padding:14px; font-size:0.8rem; color:var(--text-muted); text-align:center;">No past chats yet.</div>`;
        return;
      }

      state.conversations.forEach(c => {
        const item = document.createElement('div');
        item.className = `history-item ${c.id === state.currentConversationId ? 'active' : ''}`;
        item.innerHTML = `
          <div class="history-title" onclick="loadConversation('${c.id}')">${c.title || 'Untitled Chat'}</div>
          <button class="history-delete" onclick="deleteConversation('${c.id}', event)" title="Delete">✕</button>
        `;
        historyList.appendChild(item);
      });
    }

    async function startNewChat() {
      closeSidebarMobile();
      state.currentConversationId = null;
      state.history = [];
      state.attachments = [];
      renderAttachmentPreviews();
      chatContainer.innerHTML = '';
      chatContainer.appendChild(emptyState);
      emptyState.style.display = 'block';
      inputEl.value = '';
      inputEl.focus();
      renderHistoryList();
    }

    async function loadConversation(convId) {
      closeSidebarMobile();
      if (!state.token) return;
      state.currentConversationId = convId;
      renderHistoryList();

      try {
        const res = await fetch(`/api/conversations/${convId}`, {
          headers: { 'Authorization': `Bearer ${state.token}` }
        });
        const data = await res.json();
        if (data.success) {
          chatContainer.innerHTML = '';
          state.history = [];
          data.messages.forEach(m => {
            addMessage(m.role === 'user' ? 'You' : 'Q&A AI', m.content, m.attachments || null);
            state.history.push({ role: m.role, content: m.content });
          });
        }
      } catch (err) {}
    }

    async function deleteConversation(convId, evt) {
      evt.stopPropagation();
      if (!confirm('Are you sure you want to delete this conversation?')) return;
      try {
        await fetch(`/api/conversations/${convId}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${state.token}` }
        });
        if (state.currentConversationId === convId) {
          startNewChat();
        }
        loadConversations();
      } catch (e) {}
    }

    // Memory Logic
    async function loadMemoriesCount() {
      if (!state.token) return;
      try {
        const res = await fetch('/api/memories', {
          headers: { 'Authorization': `Bearer ${state.token}` }
        });
        const data = await res.json();
        if (data.success) {
          const keys = Object.keys(data.memories || {});
          const countEl = document.getElementById('memory-count');
          if (countEl) countEl.textContent = keys.length;
        }
      } catch (e) {}
    }

    async function openMemoryModal() {
      if (!state.token) {
        openAuthModal('login');
        return;
      }
      try {
        const res = await fetch('/api/memories', {
          headers: { 'Authorization': `Bearer ${state.token}` }
        });
        const data = await res.json();
        const listEl = document.getElementById('memory-items-list');
        listEl.innerHTML = '';

        const memories = data.memories || {};
        const keys = Object.keys(memories);

        if (!keys.length) {
          listEl.innerHTML = '<div style="color:var(--text-muted); font-style:italic;">No memories recorded yet. Ask questions and share preferences with Q&A AI!</div>';
        } else {
          keys.forEach(k => {
            const item = document.createElement('div');
            item.style.padding = '6px 0';
            item.style.borderBottom = '1px solid var(--border)';
            item.innerHTML = `<strong>${k}:</strong> <span>${memories[k]}</span>`;
            listEl.appendChild(item);
          });
        }
        memoryModal.classList.add('active');
      } catch (e) {}
    }

    function closeMemoryModal() {
      memoryModal.classList.remove('active');
    }

    async function clearMemories() {
      if (!confirm('Clear all stored memories for your account?')) return;
      await fetch('/api/memories', {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${state.token}` }
      });
      loadMemoriesCount();
      closeMemoryModal();
    }

    function openSettingsModal() {
      const sel = document.getElementById('setting-model');
      if (sel && state.model) sel.value = state.model;
      settingsModal.classList.add('active');
    }
    function closeSettingsModal() { settingsModal.classList.remove('active'); }
    function saveSettings() {
      state.model = document.getElementById('setting-model').value || state.model;
      localStorage.setItem('qa_ai_model', state.model);
      state.systemInstructions = document.getElementById('setting-system').value;
      closeSettingsModal();
    }

    // Chat rendering
    function addMessage(sender, content, attachments = null) {
      if (emptyState) emptyState.style.display = 'none';

      const isUser = (sender === 'You');
      const row = document.createElement('div');
      row.className = `message-row ${isUser ? 'user-row' : 'ai-row'}`;

      let avatar;
      if (isUser) {
        avatar = document.createElement('div');
        avatar.className = 'avatar avatar-user';
        avatar.textContent = state.user ? state.user.username.charAt(0).toUpperCase() : '👤';
      } else {
        avatar = document.createElement('img');
        avatar.className = 'avatar avatar-img';
        avatar.src = '/logo.jpg';
        avatar.alt = 'Q&A AI';
      }

      const wrapper = document.createElement('div');
      wrapper.className = 'bubble-wrapper';

      const senderLabel = document.createElement('div');
      senderLabel.className = 'sender-name';
      senderLabel.textContent = isUser ? (state.user ? state.user.username : 'You') : 'Q&A AI';
      wrapper.appendChild(senderLabel);

      const bubble = document.createElement('div');
      bubble.className = 'bubble';

      // Render attachments inside user bubble if present
      if (isUser && attachments && attachments.length > 0) {
        const attContainer = document.createElement('div');
        attContainer.className = 'bubble-attachments';
        attachments.forEach(att => {
          if (att.isImage && (att.previewUrl || att.data)) {
            const img = document.createElement('img');
            img.className = 'bubble-attach-img';
            img.src = att.previewUrl || `data:${att.type};base64,${att.data}`;
            img.alt = att.name;
            img.title = att.name;
            img.onclick = () => window.open(img.src, '_blank');
            attContainer.appendChild(img);
          } else {
            const chip = document.createElement('div');
            chip.className = 'bubble-attach-file';
            chip.innerHTML = `${att.icon || '📄'} <span>${att.name}</span> <small>(${formatFileSize(att.size)})</small>`;
            attContainer.appendChild(chip);
          }
        });
        bubble.appendChild(attContainer);
      }

      if (isUser) {
        const textNode = document.createElement('div');
        textNode.textContent = content;
        bubble.appendChild(textNode);
      } else {
        bubble.innerHTML = marked.parse(content);
        renderMath(bubble);
        attachCopyButtons(bubble);
      }

      wrapper.appendChild(bubble);
      row.appendChild(avatar);
      row.appendChild(wrapper);
      chatContainer.appendChild(row);

      chatContainer.scrollTop = chatContainer.scrollHeight;
      return bubble;
    }

    function attachCopyButtons(container) {
      const preBlocks = container.querySelectorAll('pre');
      preBlocks.forEach((pre) => {
        const code = pre.querySelector('code');
        const lang = (code.className.match(/language-(\w+)/) || [, 'code'])[1];

        const header = document.createElement('div');
        header.className = 'code-header';
        header.innerHTML = `<span>${lang}</span><button class="copy-btn">Copy</button>`;

        const copyBtn = header.querySelector('.copy-btn');
        copyBtn.addEventListener('click', async () => {
          await navigator.clipboard.writeText(code.innerText);
          copyBtn.textContent = 'Copied!';
          setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
        });

        pre.insertBefore(header, code);
      });
    }

    function showTypingIndicator() {
      const row = document.createElement('div');
      row.id = 'typing-indicator-row';
      row.className = 'message-row ai-row';
      row.innerHTML = `
        <img src="/logo.jpg" alt="Q&A AI" class="avatar avatar-img">
        <div class="bubble-wrapper">
          <div class="sender-name">Q&A AI</div>
          <div class="typing-dots">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      `;
      chatContainer.appendChild(row);
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function removeTypingIndicator() {
      const indicator = document.getElementById('typing-indicator-row');
      if (indicator) indicator.remove();
    }

    // Creates a live-updating AI bubble for streaming responses
    function addStreamingBubble() {
      if (emptyState) emptyState.style.display = 'none';

      const row = document.createElement('div');
      row.className = 'message-row ai-row';

      const avatar = document.createElement('img');
      avatar.className = 'avatar avatar-img';
      avatar.src = '/logo.jpg';
      avatar.alt = 'Q&A AI';

      const wrapper = document.createElement('div');
      wrapper.className = 'bubble-wrapper';

      const senderLabel = document.createElement('div');
      senderLabel.className = 'sender-name';
      senderLabel.textContent = 'Q&A AI';
      wrapper.appendChild(senderLabel);

      const bubble = document.createElement('div');
      bubble.className = 'bubble streaming';
      wrapper.appendChild(bubble);

      row.appendChild(avatar);
      row.appendChild(wrapper);
      chatContainer.appendChild(row);
      chatContainer.scrollTop = chatContainer.scrollHeight;

      return bubble;
    }

    // LaTeX / Math Rendering Helper
    function renderMath(element) {
      if (window.renderMathInElement && element) {
        try {
          renderMathInElement(element, {
            delimiters: [
              { left: '$$', right: '$$', display: true },
              { left: '$', right: '$', display: false },
              { left: '\\(', right: '\\)', display: false },
              { left: '\\[', right: '\\]', display: true }
            ],
            throwOnError: false
          });
        } catch (_) {}
      }
    }

    let currentAbortController = null;

    function setGeneratingState(generating) {
      state.isGenerating = generating;
      if (generating) {
        sendBtn.classList.add('btn-stop');
        sendBtn.title = 'Stop Generating';
        sendBtn.innerHTML = `
          <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
            <rect x="4" y="4" width="16" height="16" rx="3" ry="3"></rect>
          </svg>
        `;
        sendBtn.disabled = false;
      } else {
        sendBtn.classList.remove('btn-stop');
        sendBtn.title = 'Submit Question';
        sendBtn.innerHTML = `
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        `;
        sendBtn.disabled = false;
      }
    }

    async function submitQuestion() {
      // If AI is currently generating and user clicks button, treat as STOP
      if (state.isGenerating) {
        if (currentAbortController) {
          currentAbortController.abort();
        }
        return;
      }

      const question = inputEl.value.trim();
      const hasAttachments = state.attachments && state.attachments.length > 0;

      if (!question && !hasAttachments) return;

      const effectiveQuestion = question || "Please analyze the attached file/image.";
      const currentAttachments = [...state.attachments];

      currentAbortController = new AbortController();
      setGeneratingState(true);

      inputEl.value = '';
      inputEl.style.height = 'auto';

      // Clear pending attachments from input area
      state.attachments = [];
      renderAttachmentPreviews();

      addMessage('You', effectiveQuestion, currentAttachments);
      showTypingIndicator();

      const headers = { 'Content-Type': 'application/json' };
      if (state.token) headers['Authorization'] = `Bearer ${state.token}`;

      let bubble = null;
      let rawText = '';

      try {
        const payloadAttachments = currentAttachments.map(att => ({
          name: att.name,
          type: att.type,
          size: att.size,
          data: att.data,
          text: att.text
        }));

        const response = await fetch('/api/chat/stream', {
          method: 'POST',
          headers,
          signal: currentAbortController.signal,
          body: JSON.stringify({
            question: effectiveQuestion,
            history: state.history,
            model: state.model,
            system_instructions: state.systemInstructions,
            conversation_id: state.currentConversationId,
            attachments: payloadAttachments
          })
        });

        if (!response.ok || !response.body) throw new Error('Stream unavailable');

        removeTypingIndicator();
        bubble = addStreamingBubble();
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let buffer = '';
        let currentEvent = 'message';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) {
              currentEvent = 'message';
              continue;
            }

            if (trimmed.startsWith('event:')) {
              currentEvent = trimmed.slice(6).trim();
              continue;
            }

            if (!trimmed.startsWith('data:')) continue;
            const raw = trimmed.slice(5).trim();
            if (!raw) continue;

            // Handle metadata completion
            if (currentEvent === 'done') {
              try {
                const meta = JSON.parse(raw);
                if (meta.conversation_id) {
                  state.currentConversationId = meta.conversation_id;
                }
                if (meta.title) {
                  const existing = state.conversations.find(c => c.id === meta.conversation_id);
                  if (existing) {
                    existing.title = meta.title;
                  }
                  renderHistoryList();
                } else {
                  loadConversations();
                }
              } catch (_) {}
              currentEvent = 'message';
              continue;
            }

            // Handle error event
            if (currentEvent === 'error') {
              try {
                const err = JSON.parse(raw);
                bubble.innerHTML = `<div class="ai-error-banner">${err}</div>`;
              } catch (_) {
                bubble.innerHTML = `<div class="ai-error-banner">${raw}</div>`;
              }
              currentEvent = 'message';
              continue;
            }

            // Model identifier event
            if (currentEvent === 'model') {
              currentEvent = 'message';
              continue;
            }

            // Normal streaming text chunk
            try {
              const chunk = JSON.parse(raw);
              rawText += chunk;
              bubble.innerHTML = marked.parse(rawText);
              renderMath(bubble);
              chatContainer.scrollTop = chatContainer.scrollHeight;
            } catch (_) {}
            currentEvent = 'message';
          }
        }

        bubble.classList.remove('streaming');
        if (rawText) {
          bubble.innerHTML = marked.parse(rawText);
          renderMath(bubble);
          attachCopyButtons(bubble);
        }
        chatContainer.scrollTop = chatContainer.scrollHeight;

        state.history.push({ role: 'user', content: effectiveQuestion });
        state.history.push({ role: 'assistant', content: rawText });
        if (state.history.length > 20) state.history = state.history.slice(-20);
        loadMemoriesCount();

      } catch (err) {
        removeTypingIndicator();
        if (err.name === 'AbortError') {
          // Stream interrupted by user
          if (bubble) {
            bubble.classList.remove('streaming');
            if (rawText) {
              bubble.innerHTML = marked.parse(rawText);
              renderMath(bubble);
              attachCopyButtons(bubble);
            }
          }
        } else {
          addMessage('Q&A AI', `⚠️ **Network Error:** Could not contact server. Please ensure the server is running.`);
        }
      } finally {
        setGeneratingState(false);
        currentAbortController = null;
        inputEl.focus();
      }
    }

    // Startup check
    checkAuth();