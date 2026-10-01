// Sembunyikan pesan flash info setelah beberapa detik.
document.querySelectorAll(".alert-info").forEach(function (el) {
  setTimeout(function () { el.remove(); }, 4000);
});
