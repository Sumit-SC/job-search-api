/**
 * Floating "Prep" button and flyout with interview-prep in iframe (on-the-fly).
 * Include on index, jobspy, rssjobs, jobspy-tech.
 */
(function () {
    function init() {
        var btn = document.getElementById('prep-flyout-btn');
        var panel = document.getElementById('prep-flyout-panel');
        var iframe = document.getElementById('prep-flyout-iframe');
        var closeBtn = document.getElementById('prep-flyout-close');
        var overlay = document.getElementById('prep-flyout-overlay');
        if (!btn || !panel) return;

        function open() {
            panel.classList.add('prep-flyout-open');
            if (iframe && !iframe.src) iframe.src = 'interview-prep.html';
            document.body.style.overflow = 'hidden';
        }
        function close() {
            panel.classList.remove('prep-flyout-open');
            document.body.style.overflow = '';
        }

        btn.addEventListener('click', function () {
            if (panel.classList.contains('prep-flyout-open')) close();
            else open();
        });
        if (closeBtn) closeBtn.addEventListener('click', close);
        if (overlay) overlay.addEventListener('click', close);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
