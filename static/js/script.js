document.addEventListener('DOMContentLoaded', () => {
    initFlashMessages();
    initXpToasts();
    initGenderPreview();
    initNewChatPanel();
    initServiceWorker();
    initInstallPrompt();
    initLiveStatusBadges();
    initBirthdayValidation();
    initProfilePreview();
    initProfileAvatarModal();
    initWebBackButton();
    initSwipeBack();
    initHomeReelPanel();
    initCommunityTimeline();
    initReelsFeed();
    initReelUploadPreview();

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
                    textarea.value = '';
                    textarea.style.height = 'auto';
                    messagesFeed.scrollTop = messagesFeed.scrollHeight;
                    // Update streak display in chat header
                    if (typeof result.streak === 'number') {
                        const streakEl = document.querySelector('[data-chat-streak]');
                        if (streakEl) {
                            streakEl.textContent = `🖐 ${result.streak}`;
                            streakEl.title = `${result.streak}-day high-five streak`;
                            streakEl.classList.toggle('streak-badge-zero', result.streak === 0);
                        }
                        if (result.streak_xp > 0) {
                            showXpToasts([{ points: result.streak_xp, label: `🖐 ${result.streak}-day high-five streak` }]);
                        }
                    }
                } else {
                    showAppToast(result.error || 'Failed to send message');
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
        const manualSteps = promptEl.querySelector('[data-install-manual]');
        const message = promptEl.querySelector('[data-install-message]');
        const dismissedKey = 'lvl-install-dismissed';
        let deferredPrompt = null;
        let manualPromptTimer = null;

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

        const showManualInstallHelp = () => {
            if (deferredPrompt || promptEl.hidden === false) return;
            if (actionButton) {
                actionButton.hidden = true;
            }
            if (manualSteps) {
                manualSteps.hidden = false;
            }
            if (message) {
                message.textContent = 'Install LvL from your browser menu when the native install button is not available.';
            }
            showPrompt();
        };

        if (isiOS) {
            if (message) {
                message.textContent = 'Install LvL from Safari using Share, then Add to Home Screen.';
            }
            if (iosSteps) {
                iosSteps.hidden = false;
            }
            if (manualSteps) {
                manualSteps.hidden = false;
            }
            showPrompt();
        } else {
            manualPromptTimer = window.setTimeout(showManualInstallHelp, 1600);
        }

        window.addEventListener('beforeinstallprompt', (event) => {
            event.preventDefault();
            deferredPrompt = event;
            if (manualPromptTimer) {
                window.clearTimeout(manualPromptTimer);
                manualPromptTimer = null;
            }
            if (iosSteps) {
                iosSteps.hidden = true;
            }
            if (manualSteps) {
                manualSteps.hidden = true;
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
                if (!deferredPrompt) {
                    showManualInstallHelp();
                    return;
                }
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

    // AJAX Like/Repost/Mute/Friend Logic
    const ajaxForms = document.querySelectorAll('.ajax-action-form');
    ajaxForms.forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const btn = form.querySelector('button');
            if (!btn || btn.dataset.pending === '1') return;
            btn.dataset.pending = '1';
            btn.disabled = true;

            const countTarget = btn.querySelector('strong');
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
                    const action = form.dataset.action;
                    if (action === 'like') {
                        btn.classList.toggle('active', result.liked);
                        btn.classList.toggle('like-active', result.liked);
                        if (countTarget) countTarget.textContent = result.count || '0';
                    } else if (action === 'repost') {
                        btn.classList.toggle('active', result.reposted);
                        btn.classList.toggle('repost-active', result.reposted);
                        if (countTarget) countTarget.textContent = result.count || '0';
                    } else if (action === 'follow') {
                        btn.classList.toggle('active', result.following);
                        btn.textContent = result.following ? 'Unfollow' : 'Follow';
                    } else if (action === 'mute') {
                        btn.classList.toggle('active', result.active);
                        btn.textContent = result.active ? 'Muted' : 'Mute';
                    } else if (action === 'block') {
                        btn.classList.toggle('active', result.active);
                        btn.textContent = result.active ? 'Unblock' : 'Block';
                    } else if (action === 'friend') {
                        btn.classList.toggle('active', !!result.status);
                        btn.textContent = result.label || 'Add friend';
                    }
                }
            } catch (error) {
                console.error('Error performing AJAX action:', error);
                form.submit();
                return;
            } finally {
                delete btn.dataset.pending;
                btn.disabled = false;
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
                    <button type="submit" aria-label="Delete message">
                        <svg viewBox="0 0 24 24" aria-hidden="true" width="15" height="15" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12ZM8 4h3l1-1h4l1 1h3v2H8V4Z"/></svg>
                        <span class="sr-only">Delete message</span>
                    </button>
                </form>
            `
            : '';

        wrapper.innerHTML = `
            <div class="message-bubble" title="${escapeHTML(message.created_at || '')}">${escapeHTML(message.content || '').replace(/\n/g, '<br>')}</div>
            <div class="message-meta">
                <span class="message-time">${timeStr}</span>
                ${deleteForm}
            </div>
        `;
        return wrapper;
    }

    function getThemeToken(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
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
            preview.style.setProperty('--profile-preview-color', color.value || getThemeToken('--lvl-primary'));
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
            swatch.style.setProperty('--preview-color', selected.dataset.themeColor || getThemeToken('--lvl-primary'));
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

    function initFlashMessages() {
        document.querySelectorAll('.flash').forEach((flash, index) => {
            if (flash.dataset.flashReady === '1') return;
            flash.dataset.flashReady = '1';
            flash.style.setProperty('--flash-index', index);
            flash.setAttribute('tabindex', '0');
            flash.setAttribute('role', flash.classList.contains('error') ? 'alert' : 'status');
            flash.addEventListener('click', () => dismissFlash(flash));
            flash.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    dismissFlash(flash);
                }
            });
            window.setTimeout(() => dismissFlash(flash), 4800 + index * 150);
        });
    }

    function dismissFlash(flash) {
        if (!flash || flash.dataset.dismissed === '1') return;
        flash.dataset.dismissed = '1';
        flash.classList.add('is-hiding');
        window.setTimeout(() => flash.remove(), 220);
    }

    function showAppToast(message, category = 'error') {
        if (!message) return;
        const flash = document.createElement('div');
        flash.className = `flash ${category} app-toast`;
        flash.textContent = message;
        document.body.appendChild(flash);
        initFlashMessages();
    }

    function initLiveStatusBadges() {
        const badges = document.querySelectorAll('[data-live-badge]');
        if (!badges.length) return;

        const formatCount = (count) => {
            const safeCount = Number.isFinite(Number(count)) ? Math.max(0, Number(count)) : 0;
            return safeCount > 99 ? '99+' : String(safeCount);
        };

        const updateBadgeGroup = (name, count) => {
            const safeCount = Number.isFinite(Number(count)) ? Math.max(0, Number(count)) : 0;
            document.querySelectorAll(`[data-live-badge="${name}"]`).forEach((badge) => {
                badge.hidden = safeCount <= 0;
                badge.textContent = formatCount(safeCount);
                badge.setAttribute('aria-label', `${safeCount} unread ${name}`);
            });
        };

        const refresh = async () => {
            try {
                const response = await fetch('/api/live-status', { headers: { 'Accept': 'application/json' } });
                if (!response.ok) return;
                const result = await response.json();
                if (!result.success) return;
                updateBadgeGroup('notifications', result.unread_notifications);
                updateBadgeGroup('messages', result.unread_messages);
            } catch (error) {
                console.error('Live status refresh failed:', error);
            }
        };

        refresh();
        window.setInterval(refresh, 8000);
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

    function initCommunityTimeline() {
        const hub = document.querySelector('[data-community-hub]');
        if (!hub) return;

        const track = hub.querySelector('[data-community-track]');
        const tabs = Array.from(hub.querySelectorAll('[data-community-tab]'));
        const panes = Array.from(hub.querySelectorAll('[data-community-pane]'));
        if (!track || !tabs.length || !panes.length) return;

        hub.classList.add('is-enhanced');
        const tabOrder = tabs.map((tab) => tab.dataset.communityTab).filter(Boolean);

        const setActive = (key, updateHistory = false) => {
            if (!tabOrder.includes(key)) return false;

            hub.dataset.activeTab = key;
            tabs.forEach((tab) => {
                const active = tab.dataset.communityTab === key;
                tab.classList.toggle('active', active);
                if (active) {
                    tab.setAttribute('aria-current', 'page');
                } else {
                    tab.removeAttribute('aria-current');
                }
            });
            panes.forEach((pane) => {
                const active = pane.dataset.communityPane === key;
                pane.classList.toggle('active', active);
                pane.hidden = !active;
            });

            if (updateHistory) {
                const activeTab = tabs.find((tab) => tab.dataset.communityTab === key);
                if (activeTab && activeTab.href) {
                    window.history.replaceState(null, '', activeTab.href);
                }
            }

            return true;
        };

        const activateByOffset = (offset) => {
            const current = hub.dataset.activeTab || tabOrder[0];
            const currentIndex = Math.max(0, tabOrder.indexOf(current));
            const nextIndex = Math.min(tabOrder.length - 1, Math.max(0, currentIndex + offset));
            const nextKey = tabOrder[nextIndex];
            if (nextKey && nextKey !== current) {
                setActive(nextKey, true);
            }
        };

        tabs.forEach((tab) => {
            tab.addEventListener('click', (event) => {
                const key = tab.dataset.communityTab;
                if (!key) return;
                if (setActive(key, true)) {
                    event.preventDefault();
                }
            });
        });

        let pointerStart = null;
        track.addEventListener('pointerdown', (event) => {
            if (event.button !== 0) return;
            if (event.target.closest('a, button, input, textarea, select, label')) return;
            pointerStart = { x: event.clientX, y: event.clientY };
        }, { passive: true });

        track.addEventListener('pointerup', (event) => {
            if (!pointerStart) return;
            const deltaX = event.clientX - pointerStart.x;
            const deltaY = event.clientY - pointerStart.y;
            pointerStart = null;

            if (Math.abs(deltaX) < 60 || Math.abs(deltaX) < Math.abs(deltaY) * 1.35) return;
            activateByOffset(deltaX < 0 ? 1 : -1);
        }, { passive: true });

        track.addEventListener('pointercancel', () => {
            pointerStart = null;
        }, { passive: true });

        const tabNav = hub.querySelector('.community-timeline-tabs');
        if (tabNav) {
            tabNav.addEventListener('keydown', (event) => {
                if (event.key === 'ArrowLeft') {
                    event.preventDefault();
                    activateByOffset(-1);
                } else if (event.key === 'ArrowRight') {
                    event.preventDefault();
                    activateByOffset(1);
                }
            });
        }

        const initial = hub.dataset.activeTab || tabs[0].dataset.communityTab;
        setActive(initial, false);
    }

    function initReelsFeed() {
        const feed = document.querySelector('[data-reels-feed]');
        if (!feed) return;

        const cards = Array.from(feed.querySelectorAll('[data-reel-card]'));
        const viewed = new Set();
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const soundPreferenceKey = 'lvlReelsSoundOn';
        let soundOn = false;
        let activeCard = null;

        try {
            soundOn = window.sessionStorage.getItem(soundPreferenceKey) === '1';
        } catch (error) {
            soundOn = false;
        }

        const saveSoundPreference = () => {
            try {
                window.sessionStorage.setItem(soundPreferenceKey, soundOn ? '1' : '0');
            } catch (error) {
                // Session storage can be unavailable in private or restricted contexts.
            }
        };

        const updateMuteControl = (button, label, muted) => {
            if (!button) return;
            if (label) label.textContent = muted ? 'Muted' : 'Sound on';
            button.classList.toggle('active', !muted);
            button.setAttribute('aria-label', muted ? 'Unmute reels' : 'Mute reels');
        };

        const applySoundPreference = (card) => {
            const video = card.querySelector('[data-reel-video]');
            const muteButton = card.querySelector('[data-reel-mute]');
            const muteLabel = card.querySelector('[data-reel-mute-icon]');
            if (!video) return;
            video.muted = !soundOn;
            updateMuteControl(muteButton, muteLabel, video.muted);
        };

        const applySoundPreferenceToAll = () => {
            cards.forEach(applySoundPreference);
        };

        const pauseCard = (card) => {
            const video = card.querySelector('[data-reel-video]');
            if (video && !video.paused) video.pause();
            card.classList.remove('active');
        };

        const updatePlayIcon = (card) => {
            const video = card.querySelector('[data-reel-video]');
            const label = card.querySelector('[data-reel-play-icon]');
            if (!video || !label) return;
            label.textContent = video.paused ? 'Play' : 'Pause';
            card.classList.toggle('is-paused', video.paused);
        };

        const markViewed = async (card) => {
            const reelId = card.dataset.reelId;
            const viewUrl = card.dataset.viewUrl;
            if (!reelId || !viewUrl || viewed.has(reelId)) return;
            viewed.add(reelId);
            const token = card.querySelector('input[name="csrf_token"]');
            const formData = new FormData();
            formData.append('ajax', '1');
            if (token) formData.append('csrf_token', token.value);
            try {
                await fetch(viewUrl, { method: 'POST', body: formData, headers: { 'Accept': 'application/json' } });
            } catch (error) {
                console.error('Could not record reel view:', error);
            }
        };

        const retryActivePlay = (card, video) => {
            window.setTimeout(() => {
                if (card !== activeCard || !video || !video.paused || video.readyState < 2) return;
                video.play().catch(() => {
                    card.classList.add('is-paused');
                    updatePlayIcon(card);
                });
            }, 250);
        };

        const activateCard = (card) => {
            if (!card || activeCard === card) return;
            cards.forEach((item) => {
                if (item !== card) pauseCard(item);
            });
            activeCard = card;
            card.classList.add('active');
            const video = card.querySelector('[data-reel-video]');
            if (!video) return;
            applySoundPreference(card);
            if (video.paused) {
                const playPromise = video.play();
                if (playPromise && typeof playPromise.catch === 'function') {
                    playPromise.catch(() => {
                        card.classList.add('is-paused');
                        updatePlayIcon(card);
                        retryActivePlay(card, video);
                    });
                }
            }
            retryActivePlay(card, video);
            updatePlayIcon(card);
            markViewed(card);
        };

        const scrollToCard = (card) => {
            if (!card) return;
            card.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' });
        };

        const goToOffset = (offset) => {
            if (!activeCard) {
                scrollToCard(cards[0]);
                return;
            }
            const index = cards.indexOf(activeCard);
            const next = cards[Math.max(0, Math.min(cards.length - 1, index + offset))];
            scrollToCard(next);
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting && entry.intersectionRatio >= 0.7) {
                    activateCard(entry.target);
                }
            });
        }, { root: feed, threshold: [0.7] });

        cards.forEach((card) => {
            observer.observe(card);
            const video = card.querySelector('[data-reel-video]');
            const playButton = card.querySelector('[data-reel-play]');
            const muteButton = card.querySelector('[data-reel-mute]');
            const muteLabel = card.querySelector('[data-reel-mute-icon]');

            const togglePlay = () => {
                if (!video) return;
                if (video.paused) {
                    video.play().catch(() => {});
                } else {
                    video.pause();
                }
                window.setTimeout(() => updatePlayIcon(card), 0);
            };

            if (video) {
                video.addEventListener('click', togglePlay);
                video.addEventListener('play', () => updatePlayIcon(card));
                video.addEventListener('pause', () => updatePlayIcon(card));
                video.addEventListener('canplay', () => {
                    if (card !== activeCard || !video.paused) return;
                    video.play().catch(() => {
                        card.classList.add('is-paused');
                        updatePlayIcon(card);
                        retryActivePlay(card, video);
                    });
                });
                video.addEventListener('ended', () => {
                    if (card.dataset.autoplayNext === 'true') {
                        const index = cards.indexOf(card);
                        if (index < cards.length - 1) {
                            const nextCard = cards[index + 1];
                            scrollToCard(nextCard);
                            window.setTimeout(() => activateCard(nextCard), reducedMotion ? 0 : 450);
                        } else {
                            const note = document.querySelector('[data-reels-end]');
                            if (note) {
                                note.hidden = false;
                                window.setTimeout(() => { note.hidden = true; }, 1800);
                            }
                            video.currentTime = 0;
                            video.play().catch(() => {});
                        }
                    }
                });
            }

            if (playButton) playButton.addEventListener('click', togglePlay);
            if (video) applySoundPreference(card);
            if (muteButton && video) {
                muteButton.addEventListener('click', () => {
                    soundOn = video.muted;
                    saveSoundPreference();
                    applySoundPreferenceToAll();
                });
            }

            // Comment panel toggle
            const commentToggle = card.querySelector('[data-reel-comment-toggle]');
            const commentPanel = card.querySelector('[data-reel-comment-panel]');
            const commentClose = card.querySelector('[data-reel-comment-close]');

            if (commentToggle && commentPanel) {
                let commentsLoaded = false;

                const openPanel = async () => {
                    commentPanel.classList.add('is-open');
                    document.body.classList.add('reel-comments-open');
                    if (!commentsLoaded) {
                        commentsLoaded = true;
                        await loadReelComments(card, commentPanel, commentToggle);
                    }
                };

                const closePanel = () => {
                    commentPanel.classList.remove('is-open');
                    document.body.classList.remove('reel-comments-open');
                };

                commentToggle.addEventListener('click', () => {
                    if (commentPanel.classList.contains('is-open')) {
                        closePanel();
                    } else {
                        openPanel();
                    }
                });

                if (commentClose) commentClose.addEventListener('click', closePanel);

                // Comment form inside panel
                const commentForm = commentPanel.querySelector('[data-reel-comment-form]');
                if (commentForm) {
                    commentForm.addEventListener('submit', async (event) => {
                        event.preventDefault();
                        const input = commentForm.querySelector('input[name="comment"]');
                        const submitBtn = commentForm.querySelector('button[type="submit"]');
                        if (!input || !input.value.trim()) return;
                        if (submitBtn) submitBtn.disabled = true;
                        const formData = new FormData(commentForm);
                        formData.append('ajax', '1');
                        try {
                            const response = await fetch(commentForm.action, {
                                method: 'POST',
                                body: formData,
                                headers: { 'Accept': 'application/json' }
                            });
                            const result = await response.json();
                            if (!result.success) {
                                showAppToast(result.error || 'Could not post comment.');
                                return;
                            }
                            const countEl = card.querySelector('[data-reel-comment-count]');
                            if (countEl) countEl.textContent = result.count || '0';
                            const commentData = result.comment || {};
                            commentData._viewerName = commentForm.dataset.viewerName;
                            commentData._viewerUsername = commentForm.dataset.viewerUsername;
                            commentData._viewerAvatar = commentForm.dataset.viewerAvatar;
                            appendReelComment(commentPanel, commentData, true);
                            input.value = '';
                            showXpToasts(result.xp_toasts || []);
                        } catch (error) {
                            console.error('Could not post reel comment:', error);
                            commentForm.submit();
                        } finally {
                            if (submitBtn) submitBtn.disabled = false;
                        }
                    });
                }
            }
        });

        feed.querySelectorAll('[data-reel-like-form]').forEach((form) => {
            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                const btn = form.querySelector('button');
                if (btn && btn.dataset.pending === '1') return;
                if (btn) { btn.dataset.pending = '1'; btn.disabled = true; }
                const formData = new FormData(form);
                formData.append('ajax', '1');
                try {
                    const response = await fetch(form.action, { method: 'POST', body: formData, headers: { 'Accept': 'application/json' } });
                    const result = await response.json();
                    if (!result.success) {
                        showAppToast(result.error || 'Could not like reel.');
                        return;
                    }
                    if (btn) btn.classList.toggle('active', result.liked);
                    const count = form.querySelector('[data-reel-like-count]');
                    if (count) count.textContent = result.count || '0';
                    showXpToasts(result.xp_toasts || []);
                } catch (error) {
                    console.error('Could not like reel:', error);
                    form.submit();
                } finally {
                    if (btn) { delete btn.dataset.pending; btn.disabled = false; }
                }
            });
        });

        document.addEventListener('keydown', (event) => {
            if (!document.querySelector('[data-reels-feed]')) return;
            if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
            if (event.key === 'ArrowDown' || event.key === 'PageDown') {
                event.preventDefault();
                goToOffset(1);
            } else if (event.key === 'ArrowUp' || event.key === 'PageUp') {
                event.preventDefault();
                goToOffset(-1);
            } else if (event.key === ' ') {
                event.preventDefault();
                const button = activeCard ? activeCard.querySelector('[data-reel-play]') : null;
                if (button) button.click();
            } else if (event.key.toLowerCase() === 'm') {
                const button = activeCard ? activeCard.querySelector('[data-reel-mute]') : null;
                if (button) button.click();
            }
        });

        window.requestAnimationFrame(() => activateCard(cards[0]));
    }

    async function loadReelComments(card, panel, toggleBtn) {
        const listEl = panel.querySelector('[data-reel-comment-list]');
        if (!listEl) return;
        const url = toggleBtn.dataset.commentsUrl;
        if (!url) {
            listEl.innerHTML = '<p class="reel-comment-empty">Comments not available.</p>';
            return;
        }
        listEl.innerHTML = '<p class="reel-comment-empty">Loading…</p>';
        try {
            const response = await fetch(url, { headers: { 'Accept': 'application/json' } });
            const result = await response.json();
            listEl.innerHTML = '';
            if (!result.success) {
                listEl.innerHTML = `<p class="reel-comment-empty">${escapeHTML(result.error || 'Could not load comments.')}</p>`;
                return;
            }
            if (!result.comments || result.comments.length === 0) {
                listEl.innerHTML = '<p class="reel-comment-empty">No comments yet. Be the first!</p>';
                return;
            }
            result.comments.forEach((comment) => appendReelComment(panel, comment, false));
            listEl.scrollTop = listEl.scrollHeight;
        } catch (error) {
            console.error('Could not load reel comments:', error);
            listEl.innerHTML = '<p class="reel-comment-empty">Could not load comments.</p>';
        }
    }

    function appendReelComment(panel, comment, scrollToBottom) {
        const listEl = panel.querySelector('[data-reel-comment-list]');
        if (!listEl) return;
        const empty = listEl.querySelector('.reel-comment-empty');
        if (empty) empty.remove();
        const user = comment.user || {};
        const avatarSrc = user.profile_photo_url || comment._viewerAvatar || '/static/assets/default-male-avatar.svg';
        const displayName = escapeHTML(user.display_name || comment._viewerName || user.username || 'User');
        const username = escapeHTML(user.username || comment._viewerUsername || '');
        const text = escapeHTML(comment.comment || '');
        const time = comment.created_at ? new Date(comment.created_at).toLocaleDateString() : '';
        const item = document.createElement('div');
        item.className = 'reel-comment-item';
        item.innerHTML = `
            <img class="avatar reel-comment-avatar" src="${escapeHTML(avatarSrc)}" alt="">
            <div class="reel-comment-body">
                <span class="reel-comment-author">${displayName}</span>
                <span class="reel-comment-handle">@${username}</span>
                <p class="reel-comment-text">${text}</p>
                ${time ? `<time class="reel-comment-time">${time}</time>` : ''}
            </div>
        `;
        listEl.appendChild(item);
        if (scrollToBottom) listEl.scrollTop = listEl.scrollHeight;
    }

    function initProfileAvatarModal() {
        const btn = document.querySelector('[data-profile-avatar-open]');
        if (!btn) return;
        const img = btn.querySelector('img');
        if (!img || !img.src) return;

        btn.addEventListener('click', () => {
            const modal = document.createElement('div');
            modal.className = 'avatar-modal';
            modal.setAttribute('role', 'dialog');
            modal.setAttribute('aria-modal', 'true');
            modal.setAttribute('aria-label', 'Profile picture');
            modal.innerHTML = `
                <button class="avatar-modal-close" aria-label="Close">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
                </button>
                <img src="${escapeHTML(img.src)}" alt="Profile picture">
            `;
            document.body.appendChild(modal);
            window.requestAnimationFrame(() => modal.classList.add('is-open'));

            const closeModal = () => {
                modal.classList.remove('is-open');
                window.setTimeout(() => modal.remove(), 220);
            };

            modal.addEventListener('click', (e) => {
                if (e.target === modal || e.target.closest('.avatar-modal-close')) closeModal();
            });

            const keyHandler = (e) => {
                if (e.key === 'Escape') { closeModal(); document.removeEventListener('keydown', keyHandler); }
            };
            document.addEventListener('keydown', keyHandler);
        });
    }

    function initReelUploadPreview() {
        const form = document.querySelector('[data-reel-upload-form]');
        if (!form) return;

        const input = form.querySelector('[data-reel-video-input]');
        const preview = form.querySelector('[data-reel-preview]');
        const previewVideo = preview ? preview.querySelector('video') : null;
        const submit = form.querySelector('[data-reel-submit]');
        const message = form.querySelector('[data-reel-upload-message]');
        const label = form.querySelector('[data-reel-file-label]');
        const caption = form.querySelector('textarea[name="caption"]');
        const captionCount = form.querySelector('[data-reel-caption-count]');
        const visibility = form.querySelector('[data-reel-visibility]');
        const communityField = form.querySelector('[data-reel-community-field]');
        const maxBytes = parseInt(form.dataset.maxVideoBytes || '0', 10);
        const allowedTypes = new Set(['video/mp4', 'video/webm', 'video/quicktime', 'video/x-m4v']);
        let previewUrl = null;

        const setMessage = (text, isError = false) => {
            if (!message) return;
            message.textContent = text || '';
            message.classList.toggle('error', isError);
        };

        const clearPreview = () => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            previewUrl = null;
            if (previewVideo) previewVideo.removeAttribute('src');
            if (preview) preview.hidden = true;
        };

        const validateVideo = () => {
            clearPreview();
            const file = input && input.files ? input.files[0] : null;
            if (!file) {
                if (submit) submit.disabled = true;
                if (label) label.textContent = 'Choose video';
                setMessage('');
                return;
            }
            if (label) label.textContent = file.name || 'Video selected';
            if (maxBytes && file.size > maxBytes) {
                if (submit) submit.disabled = true;
                setMessage('This video is larger than the configured upload limit.', true);
                return;
            }
            if (file.type && !allowedTypes.has(file.type)) {
                if (submit) submit.disabled = true;
                setMessage('Choose an MP4, WebM, MOV, or M4V video.', true);
                return;
            }
            previewUrl = URL.createObjectURL(file);
            if (previewVideo) {
                previewVideo.src = previewUrl;
                previewVideo.load();
            }
            if (preview) preview.hidden = false;
            if (submit) submit.disabled = false;
            setMessage('Ready to upload.');
        };

        if (input) input.addEventListener('change', validateVideo);
        if (caption && captionCount) {
            caption.addEventListener('input', () => {
                captionCount.textContent = String(Math.max(0, 220 - caption.value.length));
            });
        }
        if (visibility && communityField) {
            const toggleCommunity = () => {
                communityField.hidden = visibility.value !== 'community';
            };
            visibility.addEventListener('change', toggleCommunity);
            toggleCommunity();
        }
    }

    function initHomeReelPanel() {
        const panel = document.querySelector('[data-home-reel-panel]');
        if (!panel) return;

        const slides = Array.from(panel.querySelectorAll('[data-home-reel-slide]'));
        if (!slides.length) return;

        const counter = panel.querySelector('[data-home-reel-counter]');
        let current = 0;

        const getVideo = (slide) => slide.querySelector('[data-home-reel-video]');
        const getPlayBtn = (slide) => slide.querySelector('[data-home-reel-play]');
        const getPlayIcon = (slide) => slide.querySelector('[data-play-icon]');

        const pauseSlide = (slide) => {
            const vid = getVideo(slide);
            if (vid && !vid.paused) vid.pause();
        };

        const updatePlayIcon = (slide) => {
            const vid = getVideo(slide);
            const icon = getPlayIcon(slide);
            if (!vid || !icon) return;
            // Show play icon when paused, hide when playing
            icon.style.opacity = vid.paused ? '1' : '0';
        };

        const activateSlide = (index) => {
            slides.forEach((s, i) => {
                s.classList.toggle('is-active', i === index);
                if (i !== index) pauseSlide(s);
            });
            current = index;
            if (counter) counter.textContent = `${current + 1} / ${slides.length}`;

            const activeSlide = slides[current];
            const vid = getVideo(activeSlide);
            if (vid) {
                vid.play().catch(() => {});
                updatePlayIcon(activeSlide);
                vid.addEventListener('play', () => updatePlayIcon(activeSlide), { once: false });
                vid.addEventListener('pause', () => updatePlayIcon(activeSlide), { once: false });
            }
        };

        slides.forEach((slide) => {
            const vid = getVideo(slide);
            const playBtn = getPlayBtn(slide);
            const muteBtn = slide.querySelector('[data-home-reel-mute]');

            if (vid) {
                vid.addEventListener('click', () => {
                    if (vid.paused) { vid.play().catch(() => {}); } else { vid.pause(); }
                    updatePlayIcon(slide);
                });
                vid.addEventListener('play', () => updatePlayIcon(slide));
                vid.addEventListener('pause', () => updatePlayIcon(slide));
            }

            if (playBtn && vid) {
                playBtn.addEventListener('click', () => {
                    if (vid.paused) { vid.play().catch(() => {}); } else { vid.pause(); }
                    updatePlayIcon(slide);
                });
            }

            if (muteBtn && vid) {
                muteBtn.addEventListener('click', () => {
                    vid.muted = !vid.muted;
                    muteBtn.classList.toggle('active', !vid.muted);
                    muteBtn.setAttribute('aria-label', vid.muted ? 'Unmute' : 'Mute');
                });
            }
        });

        const prevBtn = panel.querySelector('[data-home-reel-prev]');
        const nextBtn = panel.querySelector('[data-home-reel-next]');
        if (prevBtn) prevBtn.addEventListener('click', () => activateSlide((current - 1 + slides.length) % slides.length));
        if (nextBtn) nextBtn.addEventListener('click', () => activateSlide((current + 1) % slides.length));

        // Auto-play first slide when visible via IntersectionObserver
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    const vid = getVideo(slides[current]);
                    if (vid && vid.paused) vid.play().catch(() => {});
                } else {
                    pauseSlide(slides[current]);
                }
            });
        }, { threshold: 0.3 });
        observer.observe(panel);

        activateSlide(0);
    }

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
                    showAppToast('Birthday cannot be in the future.');
                    return;
                }

                let age = today.getFullYear() - date.getFullYear();
                const m = today.getMonth() - date.getMonth();
                if (m < 0 || (m === 0 && today.getDate() < date.getDate())) {
                    age--;
                }

                if (age < 14) {
                    e.preventDefault();
                    showAppToast('You must be at least 14 years old to use LvL.');
                    return;
                }

                if (age > 120 || date.getFullYear() < 1900) {
                    e.preventDefault();
                    showAppToast('Please enter a realistic birthday.');
                    return;
                }
            });
        });
    }
});

function initWebBackButton() {
    document.querySelectorAll('[data-web-back]').forEach((button) => {
        button.addEventListener('click', () => {
            if (window.history.length > 1) {
                window.history.back();
                return;
            }
            window.location.href = '/';
        });
    });
}

function initSwipeBack() {
    let startX = 0;
    let startY = 0;
    let tracking = false;

    window.addEventListener('touchstart', (event) => {
        if (!event.touches || event.touches.length !== 1) return;
        const touch = event.touches[0];
        if (touch.clientX > 28) return;
        startX = touch.clientX;
        startY = touch.clientY;
        tracking = true;
    }, { passive: true });

    window.addEventListener('touchend', (event) => {
        if (!tracking || !event.changedTouches || event.changedTouches.length !== 1) return;
        tracking = false;
        const touch = event.changedTouches[0];
        const deltaX = touch.clientX - startX;
        const deltaY = Math.abs(touch.clientY - startY);
        if (deltaX < 84 || deltaY > 70) return;
        if (window.history.length > 1) {
            window.history.back();
        }
    }, { passive: true });
}
