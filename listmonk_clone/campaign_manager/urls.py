from django.urls import path
from . import views

# URLs for Pymongo-based APIViews

urlpatterns = [
    # Subscriber URLs
    path('subscribers/', views.SubscriberListCreateAPIView.as_view(), name='subscriber-list-create'),
    path('subscribers/<str:subscriber_uuid>/', views.SubscriberDetailAPIView.as_view(), name='subscriber-detail'),
    path('subscribers/<str:subscriber_uuid>/blocklist/', views.SubscriberBlocklistAPIView.as_view(), name='subscriber-blocklist-action'), # Specific action
    path('subscribers/blocklist/', views.SubscriberBulkBlocklistAPIView.as_view(), name='subscriber-bulk-blocklist'), # Bulk action
    # TODO: Add URLs for other subscriber actions (export, bounces, query blocklist/delete, manage lists)

    # Mailing List URLs
    path('lists/', views.MailingListListCreateAPIView.as_view(), name='mailinglist-list-create'),
    path('lists/<str:list_uuid>/', views.MailingListDetailAPIView.as_view(), name='mailinglist-detail'),
    path('public/lists/', views.PublicMailingListsAPIView.as_view(), name='public-mailinglist-list'), # Unauthenticated

    # Template URLs
    path('templates/', views.TemplateListCreateAPIView.as_view(), name='template-list-create'),
    path('templates/<str:template_uuid>/', views.TemplateDetailAPIView.as_view(), name='template-detail'),
    path('templates/<str:template_uuid>/preview/', views.TemplatePreviewAPIView.as_view(), name='template-preview'),
    path('templates/<str:template_uuid>/default/', views.TemplateSetDefaultAPIView.as_view(), name='template-set-default'),

    # Campaign URLs
    path('campaigns/', views.CampaignListCreateAPIView.as_view(), name='campaign-list-create'),
    path('campaigns/<str:campaign_uuid>/', views.CampaignDetailAPIView.as_view(), name='campaign-detail'),
    path('campaigns/<str:campaign_uuid>/status/', views.CampaignStatusUpdateAPIView.as_view(), name='campaign-update-status'),
    path('campaigns/<str:campaign_uuid>/preview/', views.CampaignPreviewAPIView.as_view(), name='campaign-preview'),
    path('campaigns/<str:campaign_uuid>/test/', views.CampaignTestSendAPIView.as_view(), name='campaign-test-send'),
    # TODO: Add URLs for campaign archive, analytics, running stats.

    # Public Subscription URL
    path('public/subscription/', views.PublicSubscriptionCreateAPIView.as_view(), name='public-subscription-create'),

    # Tracking URLs
    path('track/view/<uuid:campaign_uuid>/<uuid:subscriber_uuid>/pixel.png', views.TrackViewAPI.as_view(), name='track-view'),
    path('track/click/<uuid:campaign_uuid>/<uuid:subscriber_uuid>/<uuid:link_uuid>/', views.TrackClickAPI.as_view(), name='track-click'),

    # TODO: Subscription Confirmation URL
    # path('subscriptions/confirm/<str:token>/', views.SubscriptionConfirmAPIView.as_view(), name='subscription-confirm'),
]
