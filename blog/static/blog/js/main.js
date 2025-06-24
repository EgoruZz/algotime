/**
 * Основной JavaScript файл для AlgoTime
 */

// Обработчик формы подписки
document.getElementById('newsletter-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = e.target.querySelector('input[type="email"]').value;
    
    try {
        const response = await fetch('/api/subscribe/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({ email })
        });
        
        if (response.ok) {
            showToast('Успешно!', 'Вы подписаны на обновления', 'success');
        } else {
            const data = await response.json();
            showToast('Ошибка', data.error || 'Произошла ошибка', 'danger');
        }
    } catch (error) {
        showToast('Ошибка', 'Не удалось отправить запрос', 'danger');
    }
});

// Вспомогательные функции
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function showToast(title, message, type = 'info') {
    const toastContainer = document.createElement('div');
    toastContainer.innerHTML = `
        <div class="toast align-items-center text-white bg-${type} border-0 show" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <strong>${title}</strong>: ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    toastContainer.className = 'position-fixed bottom-0 end-0 p-3';
    toastContainer.style.zIndex = '11';
    document.body.appendChild(toastContainer);
    
    setTimeout(() => {
        toastContainer.remove();
    }, 5000);
}

// Обработчик комментариев
document.querySelectorAll('.comment-form').forEach(form => {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        
        try {
            const response = await fetch(form.action, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: formData
            });
            
            if (response.ok) {
                window.location.reload();
            } else {
                const data = await response.json();
                showToast('Ошибка', data.error || 'Ошибка при отправке комментария', 'danger');
            }
        } catch (error) {
            showToast('Ошибка', 'Не удалось отправить комментарий', 'danger');
        }
    });
});

// Темная/светлая тема
const themeToggle = document.createElement('button');
themeToggle.className = 'btn btn-sm btn-outline-secondary position-fixed bottom-0 end-0 m-3';
themeToggle.innerHTML = '<i class="bi bi-moon-stars"></i>';
themeToggle.style.zIndex = '10';
themeToggle.addEventListener('click', () => {
    const html = document.documentElement;
    const isDark = html.getAttribute('data-bs-theme') === 'dark';
    
    html.setAttribute('data-bs-theme', isDark ? 'light' : 'dark');
    themeToggle.innerHTML = isDark ? '<i class="bi bi-moon-stars"></i>' : '<i class="bi bi-sun"></i>';
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
});

// Восстановление темы из localStorage
const savedTheme = localStorage.getItem('theme') || 
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
document.documentElement.setAttribute('data-bs-theme', savedTheme);
themeToggle.innerHTML = savedTheme === 'dark' ? '<i class="bi bi-sun"></i>' : '<i class="bi bi-moon-stars"></i>';

document.body.appendChild(themeToggle);

// Lazy loading изображений
if ('IntersectionObserver' in window) {
    const lazyImages = document.querySelectorAll('img.lazy');
    
    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                if (img.dataset.srcset) img.srcset = img.dataset.srcset;
                img.classList.remove('lazy');
                imageObserver.unobserve(img);
            }
        });
    });
    
    lazyImages.forEach(img => imageObserver.observe(img));
}
