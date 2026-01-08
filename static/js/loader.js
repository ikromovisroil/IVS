//(function () {
//
//    const loader = document.getElementById("page-loader");
//
//    function showLoader() {
//        if (loader) loader.style.display = "flex";
//    }
//
//    function hideLoader() {
//        if (loader) loader.style.display = "none";
//    }
//
//    // Sahifa yuklanganda
//    window.addEventListener("load", hideLoader);
//    window.addEventListener("pageshow", hideLoader);
//
//    document.addEventListener("DOMContentLoaded", function () {
//
//        // FORM submit
//        document.querySelectorAll("form").forEach(form => {
//            form.addEventListener("submit", function () {
//                showLoader();
//
//                if (form.dataset.download === "true") {
//                    setTimeout(hideLoader, 1000);
//                }
//            });
//        });
//
//        // LINK bosilganda
//        document.querySelectorAll("a").forEach(link => {
//            link.addEventListener("click", function () {
//
//                if (
//                    link.target === "_blank" ||
//                    link.href.startsWith("javascript:") ||
//                    link.href.includes("#")
//                ) return;
//
//                showLoader();
//
//                // 🔴 FILE DOWNLOAD LINK bo‘lsa
//                if (link.dataset.download === "true") {
//                    setTimeout(hideLoader, 1000);
//                }
//            });
//        });
//
//    });
//
//})();
