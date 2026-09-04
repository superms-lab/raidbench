(function () {
  const config = window.RAIDBENCH_CONFIG || {};
  const measurementId = (config.ga4MeasurementId || "").trim();
  const hasGa4 = /^G-[A-Z0-9]+$/i.test(measurementId);
  const hasFirstPartyAnalytics = config.firstPartyAnalytics !== false;
  const eventBuffer = [];
  const hostname = window.location.hostname.toLowerCase();
  const isProduction = hostname === "raidbench.com" || hostname === "www.raidbench.com";
  const privacySignal = navigator.globalPrivacyControl === true || navigator.doNotTrack === "1";

  function loadGa4() {
    if (!hasGa4) return;

    window.dataLayer = window.dataLayer || [];
    window.gtag = function gtag() {
      window.dataLayer.push(arguments);
    };

    window.gtag("js", new Date());
    window.gtag("config", measurementId, {
      send_page_view: true,
      page_title: document.title,
      page_location: window.location.href,
    });

    const script = document.createElement("script");
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
    document.head.appendChild(script);
  }

  function cleanParams(params) {
    return Object.fromEntries(
      Object.entries(params || {}).filter(([, value]) => value !== undefined && value !== null && value !== ""),
    );
  }

  function referrerHost() {
    if (!document.referrer) return "direct";

    try {
      const hostname = new URL(document.referrer).hostname.toLowerCase();
      if (hostname === window.location.hostname.toLowerCase()) return "internal";
      return hostname.slice(0, 120) || "direct";
    } catch {
      return "direct";
    }
  }

  function cleanCampaignValue(value, fallback) {
    const cleaned = String(value || "").toLowerCase().replace(/[^a-z0-9._-]/g, "_").replace(/_+/g, "_").slice(0, 100);
    return cleaned || fallback;
  }

  function campaignContext() {
    const params = new URLSearchParams(window.location.search);
    const incoming = {
      source: cleanCampaignValue(params.get("utm_source"), ""),
      medium: cleanCampaignValue(params.get("utm_medium"), ""),
      campaign: cleanCampaignValue(params.get("utm_campaign"), ""),
    };
    const hasIncoming = Boolean(incoming.source || incoming.medium || incoming.campaign);

    try {
      if (hasIncoming) sessionStorage.setItem("raidbench_campaign", JSON.stringify(incoming));
      const stored = JSON.parse(sessionStorage.getItem("raidbench_campaign") || "null");
      const context = hasIncoming ? incoming : stored || {};
      return {
        source: cleanCampaignValue(context.source, referrerHost()),
        medium: cleanCampaignValue(context.medium, referrerHost() === "direct" ? "none" : "referral"),
        campaign: cleanCampaignValue(context.campaign, "none"),
      };
    } catch {
      return { source: referrerHost(), medium: referrerHost() === "direct" ? "none" : "referral", campaign: "none" };
    }
  }

  async function recordPageView() {
    if (!hasFirstPartyAnalytics || !isProduction || privacySignal) return;

    try {
      const campaign = campaignContext();
      const response = await fetch("/api/analytics/pageview", {
        method: "POST",
        credentials: "omit",
        cache: "no-store",
        keepalive: true,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: window.location.pathname,
          referrerHost: referrerHost(),
          ...campaign,
        }),
      });

      if (config.analyticsDebug && !response.ok) {
        console.info("[RaidBenchAnalytics] Page view was not recorded", response.status);
      }
    } catch (error) {
      if (config.analyticsDebug) console.info("[RaidBenchAnalytics] Page view request failed", error);
    }
  }

  async function recordEvent(eventName) {
    if (!hasFirstPartyAnalytics || !isProduction || privacySignal) return;
    try {
      const response = await fetch("/api/analytics/event", {
        method: "POST",
        credentials: "omit",
        cache: "no-store",
        keepalive: true,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          eventName,
          pagePath: window.location.pathname,
          ...campaignContext(),
        }),
      });
      if (config.analyticsDebug && !response.ok) {
        console.info("[RaidBenchAnalytics] Event was not recorded", eventName, response.status);
      }
    } catch (error) {
      if (config.analyticsDebug) console.info("[RaidBenchAnalytics] Event request failed", eventName, error);
    }
  }

  function track(name, params = {}) {
    const payload = cleanParams({
      page_path: window.location.pathname,
      page_title: document.title,
      ...params,
    });

    eventBuffer.push({
      name,
      params: payload,
      at: new Date().toISOString(),
    });

    if (hasGa4 && typeof window.gtag === "function") {
      window.gtag("event", name, payload);
    }

    recordEvent(name);

    if (config.analyticsDebug) {
      console.info("[RaidBenchAnalytics]", name, payload);
    }
  }

  function visibleText(element) {
    return (element.textContent || element.getAttribute("aria-label") || "").trim().replace(/\s+/g, " ");
  }

  function bindClickTracking() {
    document.addEventListener("click", (event) => {
      const link = event.target.closest("a");
      const button = event.target.closest("button");

      if (link) {
        const customEvent = link.dataset.trackEvent;
        if (customEvent) {
          track(customEvent, {
            link_text: visibleText(link).slice(0, 120),
            link_url: link.href,
            asset_format: link.dataset.assetFormat,
          });
          return;
        }
        const isGuide = link.classList.contains("guide-item") || link.href.includes("/pages/");
        const isCta =
          link.classList.contains("primary-action") ||
          link.classList.contains("secondary-action") ||
          link.classList.contains("header-action");

        if (isGuide || isCta) {
          track(isGuide ? "guide_link_click" : "cta_click", {
            link_text: visibleText(link).slice(0, 120),
            link_url: link.href,
            offer_id: link.dataset.offerId,
            price_usd: link.dataset.priceUsd,
          });
        }
        return;
      }

      if (
        button &&
        button.type !== "submit" &&
        !["add-target", "reset-raid"].includes(button.id) &&
        !button.classList.contains("remove-row")
      ) {
        track("button_click", {
          button_id: button.id,
          button_text: visibleText(button).slice(0, 120),
        });
      }
    });
  }

  window.RaidBenchAnalytics = {
    track,
    events: eventBuffer,
    enabled: hasGa4 || hasFirstPartyAnalytics,
    providers: {
      firstParty: hasFirstPartyAnalytics,
      ga4: hasGa4,
    },
  };

  loadGa4();
  recordPageView();
  bindClickTracking();
})();
