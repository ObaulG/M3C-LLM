function showTab(tab) {
            document.getElementById('loginForm').classList.toggle('active', tab === 'login');
            document.getElementById('registerForm').classList.toggle('active', tab === 'register');
            document.getElementById('tabLogin').classList.toggle('active', tab === 'login');
            document.getElementById('tabRegister').classList.toggle('active', tab === 'register');
            document.getElementById('loginMessage').className = 'auth-message';
            document.getElementById('registerMessage').className = 'auth-message';
        }

        function showMessage(elId, text, type) {
            const el = document.getElementById(elId);
            el.textContent = text;
            el.className = 'auth-message ' + type;
        }

        async function handleLogin(event) {
            event.preventDefault();
            const username = document.getElementById('loginUsername').value.trim();
            const password = document.getElementById('loginPassword').value;
            const btn = document.getElementById('loginBtn');
            btn.disabled = true;
            showMessage('loginMessage', '', '');
            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: username, password: password })
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || 'Connexion &eacute;chou&eacute;e');
                }
                showLoggedIn(data.user);
            } catch (err) {
                showMessage('loginMessage', err.message, 'error');
            } finally {
                btn.disabled = false;
            }
            return false;
        }

        async function handleRegister(event) {
            event.preventDefault();
            const username = document.getElementById('regUsername').value.trim();
            const email = document.getElementById('regEmail').value.trim();
            const password = document.getElementById('regPassword').value;
            const btn = document.getElementById('registerBtn');
            btn.disabled = true;
            showMessage('registerMessage', '', '');
            try {
                const response = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: username, email: email, password: password })
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || 'Inscription &eacute;chou&eacute;e');
                }
                showLoggedIn(data.user);
            } catch (err) {
                showMessage('registerMessage', err.message, 'error');
            } finally {
                btn.disabled = false;
            }
            return false;
        }

        function showLoggedIn(user) {
            document.getElementById('authView').style.display = 'none';
            const view = document.getElementById('loggedInView');
            view.classList.add('active');
            document.getElementById('userInfo').innerHTML =
                '<strong>' + user.username + '</strong> (' + user.email + ')<br/>' +
                'R&ocirc;le : ' + user.role;
            window.location.replace('/profile');
        }

        function handleLogout() {
            fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }).finally(() => {
                location.reload();
            });
        }

        async function checkSession() {
            try {
                const response = await fetch('/api/auth/me', { credentials: 'same-origin' });
                if (response.ok) {
                    window.location.replace('/profile');
                }
            } catch (e) { /* pas de session */ }
        }

        document.addEventListener('DOMContentLoaded', checkSession);
