(() => {
  const pendingModuleRouteKey = "alchemy_pending_module_route_v1";
  try {
    window.sessionStorage.setItem(pendingModuleRouteKey, "v2");
  } catch {
    // The destination still carries ?tab=v2 when storage is unavailable.
  }

  const mobileUserAgent = /Android|iPhone|iPod|BlackBerry|IEMobile|Opera Mini|Windows Phone|Mobile/i.test(
    window.navigator.userAgent || "",
  );
  const coarseSmallScreen = Boolean(
    window.matchMedia && window.matchMedia("(hover: none) and (pointer: coarse) and (max-width: 820px)").matches,
  );
  const destination = mobileUserAgent || coarseSmallScreen ? "/h5?tab=v2" : "/?tab=v2";
  window.location.replace(destination);
})();
