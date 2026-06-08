
document.addEventListener('DOMContentLoaded', () => {
  // Share Modal Logic
  document.body.addEventListener('click', async (e) => {
    const trigger = e.target.closest('[data-share-modal-trigger]');
    if (trigger) {
      const card = trigger.closest('[data-clip-card]') || trigger.closest('[data-reel-card]');
      if (!card) return;
      const clipId = card.dataset.clipId || card.dataset.reelId;
      const modal = card.querySelector('[data-share-modal]');
      if (modal) {
        modal.removeAttribute('hidden');
        
        // Fetch friends if not already loaded
        const list = modal.querySelector('[data-share-friends-list]');
        if (list && list.querySelector('.loading-friends')) {
          try {
            const res = await fetch('/api/share/friends');
            const data = await res.json();
            if (data.success && data.friends.length > 0) {
              list.innerHTML = data.friends.map(f => `
                <div class="share-friend-item">
                  <div class="share-friend-info">
                    <img src="${f.profile_photo_url || '/static/assets/default-male-avatar.svg'}" class="avatar small-avatar" alt="">
                    <span><strong>${f.display_name}</strong><br><small>@${f.username}</small></span>
                  </div>
                  <button type="button" class="share-send-btn" data-share-send="${f.id}" data-clip-id="${clipId}">Send</button>
                </div>
              `).join('');
            } else {
              list.innerHTML = '<p class="loading-friends">No friends found to share with.</p>';
            }
          } catch (err) {
            list.innerHTML = '<p class="loading-friends">Error loading friends.</p>';
          }
        }
      }
      return;
    }
    
    const closeBtn = e.target.closest('[data-close-share]');
    if (closeBtn) {
      const modal = closeBtn.closest('[data-share-modal]');
      if (modal) modal.setAttribute('hidden', '');
      return;
    }
    
    const sendBtn = e.target.closest('[data-share-send]');
    if (sendBtn && !sendBtn.classList.contains('sent')) {
      const receiverId = sendBtn.dataset.shareSend;
      const clipId = sendBtn.dataset.clipId;
      const url = window.location.origin + '/reels#reel-' + clipId;
      const csrfToken = sendBtn.closest('.reel-card')?.querySelector('input[name="csrf_token"]')?.value || '';
      
      sendBtn.textContent = 'Sending...';
      sendBtn.disabled = true;
      
      try {
        const res = await fetch('/api/share/send', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken
          },
          body: JSON.stringify({ receiver_id: receiverId, url: url })
        });
        const data = await res.json();
        if (data.success) {
          sendBtn.textContent = 'Sent';
          sendBtn.classList.add('sent');
        } else {
          sendBtn.textContent = 'Failed';
          sendBtn.disabled = false;
        }
      } catch (err) {
        sendBtn.textContent = 'Failed';
        sendBtn.disabled = false;
      }
    }
  });
});
