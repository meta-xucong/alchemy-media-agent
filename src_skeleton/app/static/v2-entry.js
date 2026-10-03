(() => {
  const pendingModuleRouteKey = "alchemy_pending_module_route_v1";
  try {
    window.sessionStorage.setItem(pendingModuleRouteKey, "v2");
  } catch {
    // The destination still carries ?tab=v2 when storage is unavailable.
  }

  async function exchangeLoginTicket() {
    const ticket = new URLSearchParams(window.location.search).get("ticket");
    if (!ticket) return true;

    // Keep the one-time credential out of the address bar and browser history.
    const cleanUrl = new URL(window.location.href);
    cleanUrl.searchParams.delete("ticket");
    window.history.replaceState(null, "", `${cleanUrl.pathname}${cleanUrl.search}${cleanUrl.hash}`);

    try {
      const response = await fetch("/api/v2/veyra/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticket }),
      });
      if (!response.ok) throw new Error("ticket exchange rejected");
      return true;
    } catch {
      document.body.replaceChildren();
      const message = document.createElement("p");
      message.textContent = "Veyra 登录失败。请返回 Veyra 门户重新进入，或刷新重试。";
      document.body.append(message);
      return false;
    }
  }

  const mobileUserAgent = /Android|iPhone|iPod|BlackBerry|IEMobile|Opera Mini|Windows Phone|Mobile/i.test(
    window.navigator.userAgent || "",
  );
  const coarseSmallScreen = Boolean(
    window.matchMedia && window.matchMedia("(hover: none) and (pointer: coarse) and (max-width: 820px)").matches,
  );
  const destination = mobileUserAgent || coarseSmallScreen ? "/h5?tab=v2" : "/?tab=v2";
  void exchangeLoginTicket().then((authenticated) => {
    if (authenticated) window.location.replace(destination);
  });
})();
