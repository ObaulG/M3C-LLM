/**
 * auth_widget.js — Zone profil compacte dans l'en-tête.
 *
 * Bascule côté client entre :
 *  - un mini-formulaire de connexion (non connecté) ;
 *  - le nom d'utilisateur + lien vers la page de profil (connecté).
 *
 * Réutilise le même stockage de token (localStorage 'm3c_api_key') et les
 * mêmes endpoints (/api/auth/login, /api/auth/me, /api/auth/logout) que auth.html,
 * de façon à garder une seule session cohérente sur tout le portail.
 */
(function () {
    'use strict';

    var TOKEN_KEY = 'm3c_api_key';

    function getApiKey() { return localStorage.getItem(TOKEN_KEY); }
    function setApiKey(key) { localStorage.setItem(TOKEN_KEY, key); }
    function clearApiKey() { localStorage.removeItem(TOKEN_KEY); }

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
    }

    function showLoginForm() {
        var form = document.getElementById('profileLoginForm');
        var loggedIn = document.getElementById('profileLoggedIn');
        if (form) form.style.display = 'flex';
        if (loggedIn) loggedIn.style.display = 'none';
    }

    function setMessage(text, isError) {
        var el = document.getElementById('profileMessage');
        if (!el) return;
        el.textContent = text || '';
        el.style.color = isError ? '#b74420' : '#28a745';
    }

    // Connexion depuis le mini-formulaire de l'en-tête.
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
            body: JSON.stringify({ username: (username || '').trim(), password: password || '' })
        }).then(function (resp) {
            return resp.json().then(function (data) {
                if (!resp.ok) throw new Error(data.detail || 'Connexion échouée');
                setApiKey(data.api_key);
                showLoggedIn(data.user);
                setMessage('Connecté', false);
            });
        }).catch(function (err) {
            setMessage(err.message, true);
        }).finally(function () {
            if (btn) btn.disabled = false;
        });
        return false;
    };

    // Déconnexion depuis l'en-tête.
    window.profileWidgetLogout = function () {
        fetch('/api/auth/logout', { method: 'POST' }).finally(function () {
            clearApiKey();
            showLoginForm();
            setMessage('', false);
        });
    };

    // Au chargement : vérifie la session existante via /api/auth/me.
    ready(function () {
        var widget = document.getElementById('profileWidget');
        if (!widget) return; // page sans zone profil
        var apiKey = getApiKey();
        if (!apiKey) { showLoginForm(); return; }
        fetch('/api/auth/me', { headers: { 'Authorization': 'Bearer ' + apiKey } })
            .then(function (resp) {
                if (!resp.ok) throw new Error('session invalide');
                return resp.json();
            })
            .then(function (data) { showLoggedIn(data.user); })
            .catch(function () { clearApiKey(); showLoginForm(); });
    });
})();
