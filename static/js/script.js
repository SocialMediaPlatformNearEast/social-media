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
    initNewChatPanel();
    initServiceWorker();
    initInstallPrompt();
    initBirthdayValidation();
    initProfilePreview();

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
        const imageInput = composer.querySelector('input[type="file"][name="image"]');
        const imageLabel = composer.querySelector('[data-image-label]');
        const imagePreview = composer.querySelector('[data-image-preview]');
        const imagePreviewImg = imagePreview ? imagePreview.querySelector('img') : null;
        const clearImageBtn = composer.querySelector('[data-clear-image]');
        const maxLen = textarea ? parseInt(textarea.getAttribute('maxlength') || '280', 10) : 280;
        let previewUrl = null;

        if (textarea && charCount) {
            const updateComposerState = () => {
                const remaining = maxLen - textarea.value.length;
                charCount.textContent = `${remaining} left`;
                const hasImage = imageInput && imageInput.files && imageInput.files.length > 0;

                if (remaining < 0) {
                    charCount.style.color = 'var(--error-color)';
                    submitBtn.disabled = true;
                } else if (textarea.value.trim().length === 0 && !hasImage) {
                    submitBtn.disabled = true;
                } else {
                    charCount.style.color = 'var(--text-secondary)';
                    submitBtn.disabled = false;
                }
                
                // auto resize textarea
                textarea.style.height = 'auto';
                textarea.style.height = (textarea.scrollHeight) + 'px';
            };

            const clearImagePreview = () => {
                if (!imageInput) return;
                imageInput.value = '';
                if (previewUrl) {
                    URL.revokeObjectURL(previewUrl);
                    previewUrl = null;
                }
                if (imageLabel) imageLabel.textContent = 'Add image';
                if (imagePreviewImg) imagePreviewImg.removeAttribute('src');
                if (imagePreview) imagePreview.hidden = true;
                updateComposerState();
            };

            const refreshImagePreview = () => {
                if (!imageInput || !imageInput.files || !imageInput.files.length) {
                    clearImagePreview();
                    return;
                }

                const file = imageInput.files[0];
                if (imageLabel) imageLabel.textContent = file.name || 'Image selected';
                if (previewUrl) {
                    URL.revokeObjectURL(previewUrl);
                    previewUrl = null;
                }
                if (imagePreview && imagePreviewImg && file.type && file.type.startsWith('image/')) {
                    previewUrl = URL.createObjectURL(file);
                    imagePreviewImg.src = previewUrl;
                    imagePreview.hidden = false;
                } else if (imagePreview) {
                    imagePreview.hidden = true;
                }
            };

            textarea.addEventListener('input', updateComposerState);
            if (imageInput) {
                imageInput.addEventListener('change', () => {
                    refreshImagePreview();
                    updateComposerState();
                });
            }
            if (clearImageBtn) {
                clearImageBtn.addEventListener('click', clearImagePreview);
            }
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
        const textarea = chatForm.querySelector('textarea');

        if (textarea) {
            textarea.addEventListener('keydown', (event) => {
                if (event.key !== 'Enter' || event.shiftKey || event.isComposing) {
                    return;
                }

                event.preventDefault();
                if (textarea.value.trim()) {
                    chatForm.requestSubmit();
                }
            });
        }

        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const textarea = chatForm.querySelector('textarea');
            const content = textarea.value.trim();
            if (!content) return;

            const formData = new FormData(chatForm);
            formData.append('ajax', '1');

            try {
                const response = await fetch(chatForm.action, {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.success) {
                    const wrapper = renderMessage(result.message, true);
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

        const pollUrl = messagesFeed.dataset.messageApi;
        if (pollUrl) {
            window.setInterval(async () => {
                const messageEls = Array.from(messagesFeed.querySelectorAll('[data-message-id]'));
                const latest = messageEls[messageEls.length - 1];
                const sinceId = latest ? latest.dataset.messageId : '0';
                try {
                    const response = await fetch(`${pollUrl}?since_id=${encodeURIComponent(sinceId)}`, {
                        headers: { 'Accept': 'application/json' }
                    });
                    const result = await response.json();
                    if (!result.success || !Array.isArray(result.messages) || !result.messages.length) return;
                    const existing = new Set(Array.from(messagesFeed.querySelectorAll('[data-message-id]')).map(el => el.dataset.messageId));
                    result.messages.forEach((message) => {
                        if (existing.has(String(message.id))) return;
                        messagesFeed.appendChild(renderMessage(message, message.sender_id === result.viewer_id));
                    });
                    messagesFeed.scrollTop = messagesFeed.scrollHeight;
                } catch (error) {
                    console.error('Message refresh failed:', error);
                }
            }, 7000);
        }
    }

    function initNewChatPanel() {
        const panel = document.getElementById('new-chat-panel');
        const toggle = document.querySelector('[data-new-chat-toggle]');
        if (!panel || !toggle) return;

        const closeButtons = panel.querySelectorAll('[data-new-chat-close]');
        const setOpen = (open) => {
            panel.hidden = !open;
            toggle.setAttribute('aria-expanded', String(open));
            document.body.classList.toggle('new-chat-open', open);

            if (open) {
                const firstLink = panel.querySelector('.user-select-item');
                if (firstLink) firstLink.focus();
            } else {
                toggle.focus();
            }
        };

        toggle.addEventListener('click', () => setOpen(panel.hidden));
        closeButtons.forEach((button) => {
            button.addEventListener('click', () => setOpen(false));
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && !panel.hidden) {
                setOpen(false);
            }
        });
    }

    function initServiceWorker() {
        if (!('serviceWorker' in navigator)) return;
        if (!window.isSecureContext && !['localhost', '127.0.0.1'].includes(window.location.hostname)) return;

        navigator.serviceWorker.register('/service-worker.js').catch((error) => {
            console.error('Service worker registration failed:', error);
        });
    }

    function initInstallPrompt() {
        const promptEl = document.querySelector('[data-install-prompt]');
        if (!promptEl) return;

        const actionButton = promptEl.querySelector('[data-install-action]');
        const dismissButton = promptEl.querySelector('[data-install-dismiss]');
        const iosSteps = promptEl.querySelector('[data-install-ios]');
        const message = promptEl.querySelector('[data-install-message]');
        const dismissedKey = 'lvl-install-dismissed';
        let deferredPrompt = null;

        const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
        if (isStandalone || window.localStorage.getItem(dismissedKey) === '1') {
            return;
        }

        const isiOS = /iphone|ipad|ipod/i.test(window.navigator.userAgent)
            || (window.navigator.platform === 'MacIntel' && window.navigator.maxTouchPoints > 1);

        const showPrompt = () => {
            promptEl.hidden = false;
        };

        const hidePrompt = () => {
            promptEl.hidden = true;
        };

        if (isiOS) {
            if (message) {
                message.textContent = 'Install LvL from Safari using Share, then Add to Home Screen.';
            }
            if (iosSteps) {
                iosSteps.hidden = false;
            }
            showPrompt();
        }

        window.addEventListener('beforeinstallprompt', (event) => {
            event.preventDefault();
            deferredPrompt = event;
            if (iosSteps) {
                iosSteps.hidden = true;
            }
            if (actionButton) {
                actionButton.hidden = false;
            }
            if (message) {
                message.textContent = 'Put LvL on your home screen for a faster app-like experience.';
            }
            showPrompt();
        });

        if (actionButton) {
            actionButton.addEventListener('click', async () => {
                if (!deferredPrompt) return;
                deferredPrompt.prompt();
                const choice = await deferredPrompt.userChoice;
                deferredPrompt = null;
                if (choice && choice.outcome === 'accepted') {
                    window.localStorage.setItem(dismissedKey, '1');
                    hidePrompt();
                }
            });
        }

        if (dismissButton) {
            dismissButton.addEventListener('click', () => {
                window.localStorage.setItem(dismissedKey, '1');
                hidePrompt();
            });
        }

        window.addEventListener('appinstalled', () => {
            window.localStorage.setItem(dismissedKey, '1');
            hidePrompt();
        });
    }

    // Sidebar Toggle Logic
    const sidebar = document.querySelector('.left-rail');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const mobileSidebarToggle = document.querySelector('.mobile-sidebar-toggle');
    
    if (sidebar) {
        // Load state for desktop
        const isMenuOpen = localStorage.getItem('sidebar-menu-open') === 'true';
        if (isMenuOpen && window.innerWidth > 1000) {
            sidebar.classList.add('menu-open');
        }

        const toggleMenu = () => {
            sidebar.classList.toggle('menu-open');
            if (window.innerWidth > 1000) {
                localStorage.setItem('sidebar-menu-open', sidebar.classList.contains('menu-open'));
            } else {
                document.body.style.overflow = sidebar.classList.contains('menu-open') ? 'hidden' : '';
            }
        };

        if (sidebarToggle) sidebarToggle.addEventListener('click', toggleMenu);
        if (mobileSidebarToggle) mobileSidebarToggle.addEventListener('click', toggleMenu);

        // Close sidebar on mobile when clicking outside
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 1000 && sidebar.classList.contains('menu-open')) {
                if (!sidebar.contains(e.target) && (!mobileSidebarToggle || !mobileSidebarToggle.contains(e.target))) {
                    toggleMenu();
                }
            }
        });
    }

    // AJAX Like/Repost Logic
    const ajaxForms = document.querySelectorAll('.ajax-action-form');
    ajaxForms.forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const btn = form.querySelector('button');
            const countTarget = btn.querySelector('strong') || btn.querySelector('span');
            const formData = new FormData(form);
            formData.append('ajax', '1');

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.success) {
                    showXpToasts(result.xp_toasts || []);
                    if (form.dataset.action === 'like') {
                        btn.classList.toggle('active', result.liked);
                        if (countTarget) countTarget.textContent = result.count || '0';
                    } else if (form.dataset.action === 'repost') {
                        btn.classList.toggle('active', result.reposted);
                        if (countTarget) countTarget.textContent = result.count || '0';
                    } else if (form.dataset.action === 'follow') {
                        btn.classList.toggle('active', result.following);
                        btn.textContent = result.following ? 'Unfollow' : 'Follow';
                    }
                }
            } catch (error) {
                console.error('Error performing AJAX action:', error);
                form.submit();
            }
        });
    });

    document.querySelectorAll('[data-copy-url]').forEach((button) => {
        button.addEventListener('click', async () => {
            const url = button.dataset.copyUrl;
            try {
                await navigator.clipboard.writeText(url);
                button.textContent = 'Copied';
                window.setTimeout(() => {
                    button.textContent = 'Copy link';
                }, 1400);
            } catch (error) {
                window.prompt('Copy this link', url);
            }
        });
    });

    function escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function renderMessage(message, own) {
        const wrapper = document.createElement('div');
        wrapper.className = `message-bubble-wrapper ${own ? 'own' : ''}`;
        wrapper.dataset.messageId = String(message.id || '');

        const time = new Date(message.created_at);
        const timeStr = Number.isNaN(time.getTime())
            ? ''
            : time.getHours().toString().padStart(2, '0') + ':' + time.getMinutes().toString().padStart(2, '0');
        const deleteUrl = messagesFeed ? messagesFeed.dataset.deleteMessageUrl : '';
        const csrfToken = messagesFeed ? messagesFeed.dataset.csrfToken : '';
        const redirectUrl = messagesFeed ? messagesFeed.dataset.redirectUrl : '';
        const deleteForm = deleteUrl && csrfToken && message.id
            ? `
                <form action="${escapeHTML(deleteUrl)}" method="post" class="message-delete-form">
                    <input type="hidden" name="csrf_token" value="${escapeHTML(csrfToken)}">
                    <input type="hidden" name="message_id" value="${escapeHTML(String(message.id))}">
                    <input type="hidden" name="redirect" value="${escapeHTML(redirectUrl)}">
                    <button type="submit" aria-label="Delete message">Delete message</button>
                </form>
            `
            : '';

        wrapper.innerHTML = `
            <div class="message-bubble" title="${escapeHTML(message.created_at || '')}">
                ${escapeHTML(message.content || '').replace(/\n/g, '<br>')}
            </div>
            <div class="message-meta">
                <span class="message-time">${timeStr}</span>
                ${deleteForm}
            </div>
        `;
        return wrapper;
    }

    function initProfilePreview() {
        const preview = document.querySelector('[data-profile-preview]');
        if (!preview) return;

        const form = preview.closest('form');
        const avatar = preview.querySelector('.profile-preview-avatar');
        const name = preview.querySelector('[data-preview-name]');
        const username = preview.querySelector('[data-preview-username]');
        const bio = preview.querySelector('[data-preview-bio]');
        const color = form.querySelector('input[name="profile_pic"]');
        const first = form.querySelector('input[name="first_name"]');
        const last = form.querySelector('input[name="last_name"]');
        const nick = form.querySelector('input[name="nickname"]');
        const bioInput = form.querySelector('textarea[name="bio"]');
        const fileInput = form.querySelector('[data-profile-photo-input]');

        const update = () => {
            const displayName = `${first.value || ''} ${last.value || ''}`.trim() || 'Your name';
            name.textContent = displayName;
            username.textContent = `@${nick.value || 'username'}`;
            bio.textContent = bioInput.value || 'No bio yet.';
            preview.style.setProperty('--profile-preview-color', color.value || '#1D9BF0');
        };

        [first, last, nick, bioInput, color].forEach(input => input && input.addEventListener('input', update));
        if (fileInput && avatar) {
            fileInput.addEventListener('change', () => {
                const file = fileInput.files && fileInput.files[0];
                if (!file) return;
                avatar.src = URL.createObjectURL(file);
            });
        }
        update();
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
        const backButton = chat.querySelector('.support-back-button');
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

        const showQuestions = () => {
            chat.classList.remove('has-answer');
            answerList.replaceChildren();
            if (backButton) backButton.hidden = true;
            questionList.hidden = false;
            const body = chat.querySelector('.support-chat-body');
            if (body) body.scrollTop = 0;
        };

        const showAnswer = (question, answer) => {
            questionList.hidden = true;
            answerList.replaceChildren();
            appendSupportMessage(answerList, question, 'user');
            appendSupportMessage(answerList, answer, 'bot');
            chat.classList.add('has-answer');
            if (backButton) backButton.hidden = false;
            const body = chat.querySelector('.support-chat-body');
            if (body) body.scrollTop = 0;
        };

        toggle.addEventListener('click', () => setOpen(windowEl.hidden));
        close.addEventListener('click', () => setOpen(false));
        if (backButton) {
            backButton.addEventListener('click', showQuestions);
        }

        questionList.addEventListener('click', (event) => {
            const button = event.target.closest('.support-question-button');
            if (!button) return;

            const item = items[button.dataset.faqKey];
            if (!item) return;

            showAnswer(item.question, item.answer);
        });

        contactButton.addEventListener('click', () => {
            showAnswer('Still need help?', 'Use the Messages page to contact a community member or ask for help.');
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

    function initBirthdayValidation() {
        const birthdayInputs = document.querySelectorAll('input[type="date"][name="birthday"]');
        birthdayInputs.forEach(input => {
            const form = input.closest('form');
            if (!form) return;

            form.addEventListener('submit', (e) => {
                if (!input.value) return;

                const date = new Date(input.value);
                const today = new Date();
                
                if (date > today) {
                    e.preventDefault();
                    alert('Birthday cannot be in the future.');
                    return;
                }

                let age = today.getFullYear() - date.getFullYear();
                const m = today.getMonth() - date.getMonth();
                if (m < 0 || (m === 0 && today.getDate() < date.getDate())) {
                    age--;
                }

                if (age < 13) {
                    e.preventDefault();
                    alert('You must be at least 13 years old to use this app.');
                    return;
                }

                if (age > 120 || date.getFullYear() < 1900) {
                    e.preventDefault();
                    alert('Please enter a realistic birthday.');
                    return;
                }
            });
        });
    }
});
