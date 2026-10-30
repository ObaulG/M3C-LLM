/**
 * auth_widget.js — Zone profil compacte dans l'en-tête.
 *
 * Bascule côté client entre :
 *  - un mini-formulaire de connexion (non connecté) ;
 *  - le nom d'utilisateur + lien vers la page de profil (connecté).
 *
 * La session est portée par le cookie httpOnly 'm3c_api_key', posé par
 * /api/auth/login (et /api/auth/register) et lu par /api/auth/me à chaque
 * chargement de page. Le token n'est plus stocké côté client.
 */
(function () {
    'use strict';

    function ready(fn) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fn);
        } else { fn(); }
    }

    function showLoggedIn(user) {
        var form = document.getElementById('profileLoginForm');
        var loggedIn = document.getElementById('profileLoggedIn');
        var display = document.getElementById('profileUsernameDisplay');
        if (form) form.style.display = 'none';
        if (loggedIn) loggedIn.style.display = 'flex';
        if (display) display.textContent = user.username || user.email || 'Utilisateur';
        // Un utilisateur non global_admin sans cle API Mistral n'a acces qu'a
        // l'index, la page de connexion et la page de profil.
        var isGlobalAdmin = user.role === 'global_admin';
        setNavLinksDisabled(!(isGlobalAdmin || user.has_mistral_api_key));
    }

    function showLoginForm() {
        var form = document.getElementById('profileLoginForm');
        var loggedIn = document.getElementById('profileLoggedIn');
        if (form) form.style.display = 'flex';
        if (loggedIn) loggedIn.style.display = 'none';
        setNavLinksDisabled(true);
    }

    // Grise (ou réactive) les liens de navigation autres que Index / Connexion.
    // Les liens grisés ne sont plus cliquables tant que l'utilisateur n'est pas
    // connecté (la page reste de toute façon protégée côté serveur).
    function setNavLinksDisabled(disabled) {
        var allowed = ['index.html', 'auth.html', 'profile.html'];
        var links = document.querySelectorAll('a.nav-link');
        links.forEach(function (link) {
            var href = (link.getAttribute('href') || '');
            var page = href.split('?')[0].split('#')[0].split('/').pop() || 'index.html';
            if (allowed.indexOf(page) !== -1) return;
            if (disabled) {
                link.classList.add('nav-link-disabled');
                link.setAttribute('aria-disabled', 'true');
            } else {
                link.classList.remove('nav-link-disabled');
                link.removeAttribute('aria-disabled');
            }
        });
    }

    function setMessage(text, isError) {
        var el = document.getElementById('profileMessage');
        if (!el) return;
        el.textContent = text || '';
        el.style.color = isError ? '#b74420' : '#28a745';
    }

    // Connexion depuis le mini-formulaire de l'en-tête.
    // Le serveur pose le cookie de session httpOnly en réponse.
    window.profileWidgetLogin = function (event) {
        event.preventDefault();
        var username = (document.getElementById('profileUsername') || {}).value;
        var password = (document.getElementById('profilePassword') || {}).value;
        var btn = document.getElementById('profileLoginBtn');
        if (btn) btn.disabled = true;
        setMessage('', false);
        fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ username: (username || '').trim(), password: password || '' })
        }).then(function (resp) {
            return resp.json().then(function (data) {
                if (!resp.ok) throw new Error(data.detail || 'Connexion échouée');
                showLoggedIn(data.user);
                setNavLinksDisabled(false);
                setMessage('Connecté', false);
                document.dispatchEvent(new CustomEvent('profile-widget-login', { detail: data.user }));
            });
        }).catch(function (err) {
            setMessage(err.message, true);
        }).finally(function () {
            if (btn) btn.disabled = false;
        });
        return false;
    };

    // Déconnexion depuis l'en-tête : le serveur révoque le token et efface le cookie.
    window.profileWidgetLogout = function () {
        fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }).finally(function () {
            showLoginForm();
            setMessage('', false);
        });
    };

    // Au chargement : le cookie de session est envoyé automatiquement avec la requête.
    ready(function () {
        var widget = document.getElementById('profileWidget');
        if (!widget) return; // page sans zone profil
        fetch('/api/auth/me', { credentials: 'same-origin' })
            .then(function (resp) {
                if (!resp.ok) throw new Error('session invalide');
                return resp.json();
            })
            .then(function (data) { showLoggedIn(data.user); })
            .catch(function () { showLoginForm(); });
        // Si une cle est presente en localStorage mais pas sur le compte
        // serveur (ex : changement de navigateur), on la resynchronise.
        if (window.mistralApiKey && window.mistralApiKey.has && window.mistralApiKey.has()) {
            fetch('/api/auth/me', { credentials: 'same-origin' }).then(function (resp) {
                if (!resp.ok) return null;
                return resp.json();
            }).then(function (data) {
                if (data && data.user && data.user.role !== 'global_admin' && !data.user.has_mistral_api_key) {
                    window.mistralApiKey.syncToServer(window.mistralApiKey.get());
                }
            }).catch(function () {});
        }
        document.addEventListener('profile-widget-login', function () {
            setNavLinksDisabled(false);
        });
    });
})();
