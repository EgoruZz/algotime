/**
 * Comments system functionality for AlgoTime
 * Handles comment submission, replies and deletion via AJAX
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize comment system
    const commentSystem = {
        init: function() {
            this.cacheElements();
            this.bindEvents();
            this.setupCSRF();
        },

        cacheElements: function() {
            this.commentForm = document.querySelector('.comment-form');
            this.replyForms = document.querySelectorAll('.reply-form');
            this.replyButtons = document.querySelectorAll('.btn-reply');
            this.deleteButtons = document.querySelectorAll('.btn-delete');
            this.commentTextareas = document.querySelectorAll('.comment-form textarea');
        },

        bindEvents: function() {
            if (this.commentForm) {
                this.commentForm.addEventListener('submit', this.handleCommentSubmit.bind(this));
            }

            this.replyButtons.forEach(button => {
                button.addEventListener('click', this.toggleReplyForm.bind(this));
            });

            this.deleteButtons.forEach(button => {
                button.addEventListener('click', this.handleDelete.bind(this));
            });

            this.commentTextareas.forEach(textarea => {
                textarea.addEventListener('input', this.adjustTextareaHeight.bind(this));
            });
        },

        setupCSRF: function() {
            // Get CSRF token for AJAX requests
            this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        },

        handleCommentSubmit: function(e) {
            e.preventDefault();
            const form = e.target;
            const formData = new FormData(form);
            const submitButton = form.querySelector('button[type="submit"]');
            
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="bi bi-arrow-repeat"></i> Отправка...';

            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => {
                if (response.redirected) {
                    window.location.href = response.url;
                } else if (response.ok) {
                    return response.json();
                }
                throw new Error('Network response was not ok.');
            })
            .then(data => {
                if (data && data.status === 'success') {
                    window.location.reload();
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Произошла ошибка при отправке комментария');
                submitButton.disabled = false;
                submitButton.innerHTML = '<i class="bi bi-send"></i> Отправить';
            });
        },

        toggleReplyForm: function(e) {
            e.preventDefault();
            const commentId = e.target.dataset.commentId;
            const replyForm = document.querySelector(`#reply-form-${commentId}`);
            
            replyForm.classList.toggle('active');
            if (replyForm.classList.contains('active')) {
                replyForm.querySelector('textarea').focus();
            }
        },

        handleDelete: function(e) {
            e.preventDefault();
            if (!confirm('Вы уверены, что хотите удалить этот комментарий?')) {
                return;
            }

            const commentId = e.target.dataset.commentId;
            const url = `/comment/delete/${commentId}/`;
            
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ok') {
                    const commentElement = document.querySelector(`#comment-${commentId}`);
                    if (commentElement) {
                        commentElement.remove();
                        this.updateCommentsCount();
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Произошла ошибка при удалении комментария');
            });
        },

        adjustTextareaHeight: function(e) {
            const textarea = e.target;
            textarea.style.height = 'auto';
            textarea.style.height = `${textarea.scrollHeight}px`;
        },

        updateCommentsCount: function() {
            const countElement = document.querySelector('.comments-count');
            if (countElement) {
                const count = document.querySelectorAll('.comment').length;
                countElement.textContent = `(${count})`;
            }
        }
    };

    // Initialize the comment system
    commentSystem.init();
});
