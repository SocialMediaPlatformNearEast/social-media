document.addEventListener('DOMContentLoaded', () => {
    const faq = {
        update_profile: {
            question: 'How do I update my profile?',
            answer: '1. Open your profile\n2. Click Edit profile\n3. Update your details and theme color\n4. Save changes',
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
        use_post_menu: {
            question: 'What can I do from a post menu?',
            answer: '1. Open the three dots on a post\n2. View the profile or open the post\n3. Message the author when available\n4. Delete your own posts',
            action: 'post-actions-area'
        },
        handle_friends: {
            question: 'How do friend requests work?',
            answer: '1. Open someone’s profile\n2. Click Add friend\n3. Check Notifications for incoming requests\n4. Accept or decline from there',
            action: 'notifications-area'
        },
        search_help: {
            question: 'How do I find people or posts?',
            answer: '1. Open Search from the menu\n2. Type a name, username, or post text\n3. Use Top, Latest, or People to narrow results',
            action: 'search-area'
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
                charCount.textContent = `${remaining} left`;

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

    document.querySelectorAll('[data-post-menu-toggle]').forEach((toggle) => {
        const header = toggle.closest('.post-header');
        const menu = header ? header.querySelector('[data-post-menu]') : null;
        if (!menu) return;

        toggle.addEventListener('click', (event) => {
            event.stopPropagation();
            const opening = menu.hidden;
            document.querySelectorAll('[data-post-menu]').forEach((otherMenu) => {
                if (otherMenu !== menu) otherMenu.hidden = true;
            });
            document.querySelectorAll('[data-post-menu-toggle]').forEach((otherToggle) => {
                if (otherToggle !== toggle) otherToggle.setAttribute('aria-expanded', 'false');
            });
            menu.hidden = !opening;
            toggle.setAttribute('aria-expanded', String(opening));
        });
    });

    document.addEventListener('click', (event) => {
        if (event.target.closest('[data-post-menu]') || event.target.closest('[data-post-menu-toggle]')) {
            return;
        }
        document.querySelectorAll('[data-post-menu]').forEach((menu) => {
            menu.hidden = true;
        });
        document.querySelectorAll('[data-post-menu-toggle]').forEach((toggle) => {
            toggle.setAttribute('aria-expanded', 'false');
        });
    });

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
            highlight('notifications-area');
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
            'profile-picture-area': 'Update your profile details and theme color here.',
            'bio-area': 'Edit your short bio here.',
            'username-area': 'Change your username here.',
            'post-actions-area': 'Use this menu for user and post actions.',
            'notifications-area': 'Friend request actions appear in notifications.',
            'search-area': 'Search for people and posts here.'
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
