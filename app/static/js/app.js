// Sembunyikan pesan flash info setelah beberapa detik.
document.querySelectorAll(".alert-info").forEach(function (el) {
  setTimeout(function () { el.remove(); }, 4000);
});

// Konfirmasi untuk form aksi destruktif (hapus/batalkan).
document.querySelectorAll("form[data-confirm]").forEach(function (form) {
  form.addEventListener("submit", function (event) {
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
});
