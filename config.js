window.RAIDBENCH_CONFIG = {
  ga4MeasurementId: "",
  firstPartyAnalytics: true,
  analyticsDebug: false,
  premiumOffer: {
    offerId: "raid-prep-pack-9",
    paypalPaymentLink: "",
    contactEmail: "support@raidbench.com",
  },
  isLiveCommerceReady(apiConfig) {
    return Boolean(
      apiConfig?.mode === "production" &&
        apiConfig?.checkoutEnabled === true &&
        apiConfig?.paypalEnvironment === "live" &&
        apiConfig?.paypalWebhookReady === true &&
        apiConfig?.liveReadiness?.merchantIdentityReady === true &&
        apiConfig?.liveReadiness?.taxPolicyConfirmed === true,
    );
  },
};
