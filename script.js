document.addEventListener('DOMContentLoaded', () => {
    const faq = {
        change_cover: {
            question: 'How can I change my cover photo?',
            answer: '1. Go to your profile\n2. Click Edit profile\n3. Choose a new cover photo\n4. Save changes',
            action: 'cover-photo-area'
        },
        update_profile_picture: {
            question: 'How do I update my profile picture?',
            answer: '1. Go to your profile\n2. Click Edit profile\n3. Choose your profile picture or theme color\n4. Save changes',
            action: 'profile-picture-area'
        },
        edit_bio: {
            question: 'How can I edit my bio?',
            answer: '1. Open your profile\n2. Click Edit profile\n3. Write your new bio\n4. Click Save Changes',
            action: 'bio-area'
        },
        change_username: {
            question: 'How do I change my username?',
            answer: '1. Open Edit profile\n2. Find Username / Nickname\n3. Type your new username\n4. Save changes',
            action: 'username-area'
        },
        private_account: {
            question: 'How can I make my account private?',
            answer: '1. Open your account settings\n2. Find Privacy\n3. Turn on Private account\n4. Save your choice',
            action: 'account-area'
        },
        delete_account: {
            question: 'How do I delete my account?',
            answer: '1. Open your account settings\n2. Go to Account\n3. Choose Delete account\n4. Read the warning and confirm',
            action: 'account-area'
        },
        report_user: {
            question: 'How do I report a user?',
            answer: '1. Go to the user profile or post\n2. Click the three dots button\n3. Choose Report\n4. Pick a reason and send it',
            action: 'post-actions-area'
        },
        block_someone: {
            question: 'How do I block someone?',
            answer: '1. Go to the person profile\n2. Click the three dots button\n3. Choose Block\n4. Confirm your choice',
            action: 'post-actions-area'
        },
        reset_password: {
            question: 'How can I reset my password?',
            answer: '1. Go to the login page\n2. Click Forgot password\n3. Type your email\n4. Follow the reset steps',
            action: 'password-reset-area'
        },
        photo_upload_issue: {
            question: 'Why can’t I upload a photo?',
            answer: '1. Check that the image link is correct\n2. Use a valid photo URL\n3. Try a smaller image\n4. Save or post again',
            action: 'photo-upload-area'
        }
    };

    initSupportChat(faq);
    initXpToasts();
    initGenderPreview();

    // Auth Tabs Logic
    const authTabs = document.querySelectorAll('[data-auth-tab]');
    const authPanels = document.querySelectorAll('[data-auth-panel]');

    authTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active classes
            authTabs.forEach(t => t.classList.remove('active'));
            authPanels.forEach(p => p.classList.remove('active'));

            // Add active classes
            tab.classList.add('active');
            const targetPanel = tab.getAttribute('data-auth-tab');
            const panel = document.querySelector(`[data-auth-panel="${targetPanel}"]`);
            if (panel) {
                panel.classList.add('active');
            }
        });
    });

    // Composer Character Count Logic
    const composers = document.querySelectorAll('.composer');
    composers.forEach(composer => {
        const textarea = composer.querySelector('textarea');
        const charCount = composer.querySelector('.char-count');
        const submitBtn = composer.querySelector('button[type="submit"]');
        const maxLen = textarea ? parseInt(textarea.getAttribute('maxlength') || '280', 10) : 280;

        if (textarea && charCount) {
            textarea.addEventListener('input', () => {
                const remaining = maxLen - textarea.value.length;
                charCount.textContent = remaining;

                if (remaining < 0) {
                    charCount.style.color = 'var(--error-color)';
                    submitBtn.disabled = true;
                } else if (textarea.value.trim().length === 0) {
                    submitBtn.disabled = true;
                } else {
                    charCount.style.color = 'var(--text-secondary)';
                    submitBtn.disabled = false;
                }
                
                // auto resize textarea
                textarea.style.height = 'auto';
                textarea.style.height = (textarea.scrollHeight) + 'px';
            });
            // trigger on load
            textarea.dispatchEvent(new Event('input'));
        }
    });

    // Auto resize utility for other textareas if needed
    const textareas = document.querySelectorAll('textarea:not(.composer textarea)');
    textareas.forEach(ta => {
        ta.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
    });

    // AJAX Messaging Logic
    const chatForm = document.querySelector('.chat-input-form');
    const messagesFeed = document.getElementById('messages-feed');

    if (chatForm && messagesFeed) {
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const textarea = chatForm.querySelector('textarea');
            const content = textarea.value.trim();
            if (!content) return;

            const formData = new FormData(chatForm);
            formData.append('ajax', '1');

            try {
                const response = await fetch('actions.php', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.success) {
                    // Create message bubble
                    const wrapper = document.createElement('div');
                    wrapper.className = 'message-bubble-wrapper own';
                    
                    const time = new Date(result.message.created_at);
                    const timeStr = time.getHours().toString().padStart(2, '0') + ':' + time.getMinutes().toString().padStart(2, '0');

                    wrapper.innerHTML = `
                        <div class="message-bubble" title="${result.message.created_at}">
                            ${escapeHTML(result.message.content).replace(/\n/g, '<br>')}
                        </div>
                        <span class="message-time">${timeStr}</span>
                    `;

                    messagesFeed.appendChild(wrapper);
                    
                    // Reset form
                    textarea.value = '';
                    textarea.style.height = 'auto';
                    messagesFeed.scrollTop = messagesFeed.scrollHeight;
                } else {
                    alert(result.error || 'Failed to send message');
                }
            } catch (error) {
                console.error('Error sending message:', error);
                // Fallback to normal form submission if AJAX fails
                chatForm.submit();
            }
        });
    }

    // Sidebar Toggle Logic
    const sidebar = document.querySelector('.left-rail');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    
    if (sidebar && sidebarToggle) {
        // Load state
        const isMenuOpen = localStorage.getItem('sidebar-menu-open') === 'true';
        if (isMenuOpen) {
            sidebar.classList.add('menu-open');
        }

        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('menu-open');
            localStorage.setItem('sidebar-menu-open', sidebar.classList.contains('menu-open'));
        });
    }

    // AJAX Like/Repost Logic
    const ajaxForms = document.querySelectorAll('.ajax-action-form');
    ajaxForms.forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const btn = form.querySelector('button');
            const span = btn.querySelector('span');
            const formData = new FormData(form);
            formData.append('ajax', '1');

            try {
                const response = await fetch('actions.php', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.success) {
                    showXpToasts(result.xp_toasts || []);
                    if (form.dataset.action === 'like') {
                        btn.classList.toggle('active', result.liked);
                        span.textContent = result.count || '';
                    } else if (form.dataset.action === 'repost') {
                        btn.classList.toggle('active', result.reposted);
                        span.textContent = result.count || '';
                    } else if (form.dataset.action === 'follow') {
                        btn.classList.toggle('active', result.following);
                        btn.textContent = result.following ? 'Following' : 'Follow';
                    }
                }
            } catch (error) {
                console.error('Error performing AJAX action:', error);
                form.submit();
            }
        });
    });

    function escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function initXpToasts() {
        const data = document.getElementById('xp-toast-data');
        if (!data) return;

        try {
            showXpToasts(JSON.parse(data.textContent || '[]'));
        } catch (error) {
            console.error('Could not read XP toast data:', error);
        }
    }

    function initGenderPreview() {
        const genderInputs = document.querySelectorAll('input[name="gender"][data-avatar-url]');
        const preview = document.querySelector('[data-gender-preview]');
        const avatar = document.querySelector('[data-gender-avatar]');
        const swatch = document.querySelector('[data-gender-swatch]');

        if (!genderInputs.length || !preview || !avatar || !swatch) return;

        const updatePreview = () => {
            const selected = document.querySelector('input[name="gender"][data-avatar-url]:checked');

            if (!selected) {
                preview.hidden = true;
                return;
            }

            avatar.src = selected.dataset.avatarUrl || '';
            swatch.style.setProperty('--preview-color', selected.dataset.themeColor || '#1D9BF0');
            preview.hidden = false;
        };

        genderInputs.forEach(input => {
            input.addEventListener('change', updatePreview);
        });
        updatePreview();
    }

    function showXpToasts(toasts) {
        if (!Array.isArray(toasts) || toasts.length === 0) return;

        let stack = document.querySelector('.xp-toast-stack');
        if (!stack) {
            stack = document.createElement('div');
            stack.className = 'xp-toast-stack';
            document.body.appendChild(stack);
        }

        toasts.forEach((toast, index) => {
            const item = document.createElement('div');
            item.className = `xp-toast ${toast.type === 'level' ? 'level-up' : ''}`;
            item.textContent = toast.message || '';
            stack.appendChild(item);

            window.setTimeout(() => {
                item.classList.add('show');
            }, index * 120);

            window.setTimeout(() => {
                item.classList.remove('show');
                window.setTimeout(() => item.remove(), 220);
            }, 2600 + index * 300);
        });
    }

    function initSupportChat(items) {
        const chat = document.querySelector('.support-chat');
        if (!chat) return;

        const toggle = chat.querySelector('.support-chat-toggle');
        const close = chat.querySelector('.support-chat-close');
        const windowEl = chat.querySelector('.support-chat-window');
        const questionList = chat.querySelector('.support-question-list');
        const answerList = chat.querySelector('.support-answer-list');
        const contactButton = chat.querySelector('.support-contact-button');

        Object.entries(items).forEach(([key, item]) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'support-question-button';
            button.textContent = item.question;
            button.dataset.faqKey = key;
            questionList.appendChild(button);
        });

        const setOpen = (open) => {
            windowEl.hidden = !open;
            toggle.setAttribute('aria-expanded', String(open));
            chat.classList.toggle('is-open', open);
        };

        toggle.addEventListener('click', () => setOpen(windowEl.hidden));
        close.addEventListener('click', () => setOpen(false));

        questionList.addEventListener('click', (event) => {
            const button = event.target.closest('.support-question-button');
            if (!button) return;

            const item = items[button.dataset.faqKey];
            if (!item) return;

            appendSupportMessage(answerList, item.question, 'user');
            appendSupportMessage(answerList, item.answer, 'bot');
            answerList.scrollTop = answerList.scrollHeight;
            highlight(item.action);
        });

        contactButton.addEventListener('click', () => {
            appendSupportMessage(answerList, 'Still need help?', 'user');
            appendSupportMessage(answerList, 'Contact support: support@xapp.local', 'bot');
            answerList.scrollTop = answerList.scrollHeight;
            highlight('account-area');
        });
    }

    function appendSupportMessage(container, text, type) {
        const message = document.createElement('div');
        message.className = `support-message ${type}`;

        if (type === 'bot' && /^\d+\./m.test(text)) {
            const list = document.createElement('ol');
            text.split('\n').forEach((line) => {
                const cleanLine = line.replace(/^\d+\.\s*/, '').trim();
                if (!cleanLine) return;

                const item = document.createElement('li');
                item.textContent = cleanLine;
                list.appendChild(item);
            });
            message.appendChild(list);
        } else {
            message.textContent = text;
        }

        container.appendChild(message);
    }

    function highlight(targetName) {
        const previous = document.querySelector('.guide-highlight');
        const tooltip = document.querySelector('.guide-tooltip');
        if (previous) {
            previous.classList.remove('guide-highlight');
        }
        if (!tooltip) return;

        const target = findGuideTarget(targetName) || document.querySelector('.support-chat-window');
        if (!target) return;

        const labels = {
            'cover-photo-area': 'This is the cover photo area.',
            'profile-picture-area': 'Update your profile picture or theme color here.',
            'bio-area': 'Edit your short bio here.',
            'username-area': 'Change your username here.',
            'account-area': 'Account options live in this area.',
            'post-actions-area': 'Use this menu for user and post actions.',
            'photo-upload-area': 'Add a valid image URL here.',
            'password-reset-area': 'Start password help from the login form.'
        };

        target.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
        target.classList.add('guide-highlight');

        window.setTimeout(() => {
            const rect = target.getBoundingClientRect();
            const left = Math.min(Math.max(rect.left + 12, 16), window.innerWidth - 280);
            const top = rect.bottom + 12 > window.innerHeight - 70 ? rect.top - 58 : rect.bottom + 12;

            tooltip.textContent = labels[targetName] || 'Look here.';
            tooltip.style.left = `${left}px`;
            tooltip.style.top = `${Math.max(top, 16)}px`;
            tooltip.hidden = false;
        }, 250);

        window.clearTimeout(highlight.hideTimer);
        highlight.hideTimer = window.setTimeout(() => {
            target.classList.remove('guide-highlight');
            tooltip.hidden = true;
        }, 4500);
    }

    function findGuideTarget(targetName) {
        const targets = Array.from(document.querySelectorAll(`[data-guide-target="${targetName}"]`));
        return targets.find((target) => {
            const rect = target.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
        }) || targets[0] || null;
    }

    window.highlight = highlight;

    // Auto-focus composer if URL has compose=1
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('compose') === '1') {
        const composerTextarea = document.querySelector('.composer textarea');
        if (composerTextarea) {
            composerTextarea.focus();
            // Scroll to top to ensure it's visible
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    }
});
