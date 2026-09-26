function showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) { modal.style.display = "block"; document.body.style.overflow = "hidden"; }
    }
    function hideModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) { modal.style.display = "none"; document.body.style.overflow = "auto"; }
    }
    window.onclick = function(event) {
        const modals = document.getElementsByClassName("modal");
        for (let modal of modals) {
            if (event.target === modal) { modal.style.display = "none"; document.body.style.overflow = "auto"; }
        }
    }
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) { target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
        });
    });
    const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -50px 0px' };
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    document.querySelectorAll('.section').forEach(section => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(20px)';
        section.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(section);
    });
