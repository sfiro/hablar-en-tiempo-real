// Perfil de Firefox para el modo kiosko de v11, validado en hardware real
// (Raspberry Pi 5, 22/08/2026). Copiado por start_browser.sh a
// /tmp/ff-v11-profile/user.js si no existe todavía — ver ese script.
user_pref("media.navigator.permission.disabled", true);  // no preguntar permiso de micro
user_pref("media.autoplay.default", 0);                  // permitir reproducir audio sin gesto del usuario
user_pref("media.autoplay.blocking_policy", 0);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.aboutwelcome.enabled", false);
