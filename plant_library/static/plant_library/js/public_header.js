/* The signed-out Plant Library bar copies the landing page's: it floats over the top
   of the sheet, then condenses into a cream pill once the page scrolls. A member keeps
   the floating sidebar instead, so this does nothing when the body has a sidebar. */
(function () {
    var nav = document.querySelector('.site-navbar');
    if (!nav || document.body.classList.contains('has-sidebar')) return;

    var waiting = false;

    function sync() {
        nav.classList.toggle('is-scrolled', window.scrollY > 24);
        waiting = false;
    }

    sync();
    window.addEventListener('scroll', function () {
        if (waiting) return;
        waiting = true;
        window.requestAnimationFrame(sync);
    }, { passive: true });
})();
