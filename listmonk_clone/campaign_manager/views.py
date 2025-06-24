from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.http import HttpResponse, HttpResponseRedirect, Http404
from PIL import Image # For generating 1x1 pixel image
from bson import ObjectId # For converting string IDs to ObjectIds for DAL
import uuid # For validating UUIDs

from . import tasks # Import tasks module
from listmonk_clone.listmonk_clone.mongo_client import get_db # For direct db access if DAL doesn't cover a specific case

# Import DAL modules
from .db_access import subscribers_db, mailing_lists_db, subscriptions_db, templates_db, campaigns_db
# Import new serializers
from .serializers import (
    SubscriberInputSerializer, SubscriberOutputSerializer,
    MailingListInputSerializer, MailingListOutputSerializer, PublicMailingListOutputSerializer,
    TemplateInputSerializer, TemplateOutputSerializer,
    CampaignInputSerializer, CampaignOutputSerializer,
    PublicSubscriptionRequestSerializer, CampaignStatusUpdateSerializer, CampaignTestSendSerializer,
    BulkSubscribersActionSerializer, QueryBasedSubscribersActionSerializer, SubscriberListManagementSerializer,
    # Add other serializers as needed
)

# --- Helper function for pagination output ---
def get_paginated_response_data(results, total_count, page, per_page):
    return {
        "count": total_count,
        "next": f"?page={page + 1}&per_page={per_page}" if (page * per_page) < total_count else None,
        "previous": f"?page={page - 1}&per_page={per_page}" if page > 1 else None,
        "results": results
    }

# --- Subscriber Views ---
class SubscriberListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated] # Example permission

    def get(self, request):
        # TODO: Implement filtering from query params (query, list_id, subscription_status)
        # TODO: Implement ordering from query params
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 20))

        # Construct filter based on Listmonk's API (e.g., `query` for email/name, `list_id`)
        mongo_filter = {}
        query_param = request.query_params.get('query')
        if query_param:
            mongo_filter["$or"] = [
                {"email": {"$regex": query_param, "$options": "i"}},
                {"name": {"$regex": query_param, "$options": "i"}}
            ]
        # list_id filtering would be more complex, involving subscriptions collection.
        # This might require a more complex DAL function or aggregation.

        subscribers_data, total_count = subscribers_db.get_subscribers(
            query_filter=mongo_filter, page=page, per_page=per_page
        )
        serializer = SubscriberOutputSerializer(subscribers_data, many=True)
        return Response(get_paginated_response_data(serializer.data, total_count, page, per_page))

    def post(self, request):
        serializer = SubscriberInputSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Check for preconfirm_subscriptions, Listmonk API has this.
                # preconfirm = request.data.get('preconfirm_subscriptions', False)
                # list_uuids_to_subscribe = request.data.get('lists', []) # list of UUIDs

                subscriber_doc = subscribers_db.create_subscriber(**serializer.validated_data)

                # TODO: Handle subscriptions to lists if `list_uuids_to_subscribe` is provided.
                # This would involve:
                # 1. Fetching list ObjectIds from UUIDs.
                # 2. Calling subscriptions_db.add_subscription for each.
                # 3. Potentially triggering opt-in emails via tasks.send_optin_email_task.

                output_serializer = SubscriberOutputSerializer(subscriber_doc)
                return Response(output_serializer.data, status=status.HTTP_201_CREATED)
            except ValueError as ve: # e.g., duplicate email
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"detail": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SubscriberDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_object_by_uuid_or_404(self, subscriber_uuid):
        try:
            # Validate if it's a UUID, Pymongo find_one won't error on wrong format for string field.
            uuid.UUID(subscriber_uuid)
        except ValueError:
            raise Http404("Invalid UUID format.")

        subscriber = subscribers_db.get_subscriber_by_uuid(subscriber_uuid)
        if not subscriber:
            raise Http404("Subscriber not found.")
        return subscriber

    def get(self, request, subscriber_uuid):
        subscriber = self._get_object_by_uuid_or_404(subscriber_uuid)
        # TODO: Populate 'lists' field in serializer similar to Listmonk (name, type, subscription_status)
        # This requires fetching from subscriptions_db and mailing_lists_db.
        serializer = SubscriberOutputSerializer(subscriber)
        return Response(serializer.data)

    def put(self, request, subscriber_uuid):
        subscriber = self._get_object_by_uuid_or_404(subscriber_uuid) # Check existence
        serializer = SubscriberInputSerializer(data=request.data, partial=False) # PUT requires all fields
        if serializer.is_valid():
            try:
                modified_count = subscribers_db.update_subscriber(subscriber_uuid, serializer.validated_data)
                if modified_count > 0:
                    updated_subscriber = subscribers_db.get_subscriber_by_uuid(subscriber_uuid)
                    return Response(SubscriberOutputSerializer(updated_subscriber).data)
                return Response({"detail": "Subscriber not found or no changes made."}, status=status.HTTP_404_NOT_FOUND) # Or 200 if no change is ok
            except ValueError as ve:
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, subscriber_uuid):
        subscriber = self._get_object_by_uuid_or_404(subscriber_uuid) # Check existence
        serializer = SubscriberInputSerializer(data=request.data, partial=True) # PATCH allows partial
        if serializer.is_valid():
            try:
                modified_count = subscribers_db.update_subscriber(subscriber_uuid, serializer.validated_data)
                if modified_count > 0:
                    updated_subscriber = subscribers_db.get_subscriber_by_uuid(subscriber_uuid)
                    return Response(SubscriberOutputSerializer(updated_subscriber).data)
                # If no fields were actually changed, modified_count might be 0.
                # Return current state or a specific "no content" if appropriate.
                current_subscriber = subscribers_db.get_subscriber_by_uuid(subscriber_uuid)
                return Response(SubscriberOutputSerializer(current_subscriber).data)

            except ValueError as ve:
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def delete(self, request, subscriber_uuid):
        deleted_count = subscribers_db.delete_subscriber(subscriber_uuid)
        if deleted_count > 0:
            return Response(status=status.HTTP_204_NO_CONTENT)
        raise Http404("Subscriber not found.")

# --- Subscriber Actions ---
class SubscriberBlocklistAPIView(APIView): # Corresponds to PUT /api/subscribers/{id}/blocklist
    permission_classes = [permissions.IsAuthenticated]
    def put(self, request, subscriber_uuid):
        subscriber = subscribers_db.get_subscriber_by_uuid(subscriber_uuid)
        if not subscriber:
            raise Http404("Subscriber not found.")
        subscribers_db.update_subscriber(subscriber_uuid, {"status": "blocklisted"})
        return Response({"data": True})

class SubscriberBulkBlocklistAPIView(APIView): # Corresponds to PUT /api/subscribers/blocklist
    permission_classes = [permissions.IsAuthenticated]
    def put(self, request):
        serializer = BulkSubscribersActionSerializer(data=request.data)
        if serializer.is_valid():
            subscriber_uuids = serializer.validated_data['ids']
            # Here, 'ids' could be UUIDs or ObjectIds. Assuming UUIDs from API.
            modified_count = subscribers_db.blocklist_subscribers_by_ids(subscriber_uuids)
            return Response({"data": True, "modified_count": modified_count})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# TODO: Implement other subscriber actions: export, bounces, query blocklist/delete, manage lists

# --- Mailing List Views ---
class MailingListListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 20))
        # TODO: Filtering by query, status, tag
        lists_data, total_count = mailing_lists_db.get_mailing_lists(page=page, per_page=per_page)
        serializer = MailingListOutputSerializer(lists_data, many=True)
        return Response(get_paginated_response_data(serializer.data, total_count, page, per_page))

    def post(self, request):
        serializer = MailingListInputSerializer(data=request.data)
        if serializer.is_valid():
            try:
                list_doc = mailing_lists_db.create_mailing_list(**serializer.validated_data)
                output_serializer = MailingListOutputSerializer(list_doc)
                return Response(output_serializer.data, status=status.HTTP_201_CREATED)
            except ValueError as ve:
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MailingListDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def _get_object_by_uuid_or_404(self, list_uuid):
        mlist = mailing_lists_db.get_mailing_list_by_uuid(list_uuid)
        if not mlist:
            raise Http404("Mailing list not found.")
        # Manually add subscriber_count if not denormalized or DAL doesn't add it.
        mlist['subscriber_count'] = subscriptions_db.count_subscribers_for_list(mlist['_id'])
        return mlist

    def get(self, request, list_uuid):
        mlist = self._get_object_by_uuid_or_404(list_uuid)
        serializer = MailingListOutputSerializer(mlist)
        return Response(serializer.data)

    def put(self, request, list_uuid):
        self._get_object_by_uuid_or_404(list_uuid) # Check existence
        serializer = MailingListInputSerializer(data=request.data)
        if serializer.is_valid():
            modified_count = mailing_lists_db.update_mailing_list(list_uuid, serializer.validated_data)
            if modified_count > 0:
                updated_list = self._get_object_by_uuid_or_404(list_uuid) # Re-fetch with count
                return Response(MailingListOutputSerializer(updated_list).data)
            return Response({"detail": "List not found or no changes made."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, list_uuid):
        deleted_count = mailing_lists_db.delete_mailing_list(list_uuid)
        if deleted_count > 0:
            return Response(status=status.HTTP_204_NO_CONTENT)
        raise Http404("Mailing list not found.")

class PublicMailingListsAPIView(APIView):
    authentication_classes = []
    permission_classes = []
    def get(self, request):
        public_lists = mailing_lists_db.get_public_mailing_lists()
        serializer = PublicMailingListOutputSerializer(public_lists, many=True)
        return Response(serializer.data)


# --- Template Views ---
class TemplateListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 20))
        templates_data, total_count = templates_db.get_templates(page=page, per_page=per_page)
        serializer = TemplateOutputSerializer(templates_data, many=True)
        return Response(get_paginated_response_data(serializer.data, total_count, page, per_page))

    def post(self, request):
        serializer = TemplateInputSerializer(data=request.data)
        if serializer.is_valid():
            template_doc = templates_db.create_template(**serializer.validated_data)
            output_serializer = TemplateOutputSerializer(template_doc)
            return Response(output_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TemplateDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def _get_object_by_uuid_or_404(self, template_uuid):
        template = templates_db.get_template_by_uuid(template_uuid)
        if not template:
            raise Http404("Template not found.")
        return template

    def get(self, request, template_uuid):
        template = self._get_object_by_uuid_or_404(template_uuid)
        serializer = TemplateOutputSerializer(template)
        return Response(serializer.data)

    def put(self, request, template_uuid):
        self._get_object_by_uuid_or_404(template_uuid) # Check existence
        serializer = TemplateInputSerializer(data=request.data)
        if serializer.is_valid():
            modified_count = templates_db.update_template(template_uuid, serializer.validated_data)
            if modified_count > 0:
                updated_template = templates_db.get_template_by_uuid(template_uuid)
                return Response(TemplateOutputSerializer(updated_template).data)
            return Response({"detail": "Template not found or no changes made."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, template_uuid):
        deleted_count = templates_db.delete_template(template_uuid)
        if deleted_count > 0:
            return Response(status=status.HTTP_204_NO_CONTENT)
        raise Http404("Template not found.")

class TemplatePreviewAPIView(APIView): # GET /api/templates/{id}/preview
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, template_uuid):
        template = templates_db.get_template_by_uuid(template_uuid)
        if not template:
            raise Http404("Template not found.")
        # Basic preview, actual rendering might involve template engine with context
        return HttpResponse(template.get("body_html", ""), content_type='text/html')

class TemplateSetDefaultAPIView(APIView): # PUT /api/templates/{id}/default
    permission_classes = [permissions.IsAuthenticated]
    def put(self, request, template_uuid):
        success = templates_db.set_template_as_default(template_uuid)
        if success:
            updated_template = templates_db.get_template_by_uuid(template_uuid)
            return Response(TemplateOutputSerializer(updated_template).data)
        raise Http404("Template not found or could not be set as default.")


# --- Campaign Views ---
class CampaignListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 20))
        # TODO: Filtering from query params
        campaigns_data, total_count = campaigns_db.get_campaigns(page=page, per_page=per_page)

        # Enrich data (template_info, target_lists_info) if not done by DAL $lookup
        # This is an example of application-level enrichment
        db = get_db()
        for camp in campaigns_data:
            if camp.get("template_id"):
                template = db[templates_db.TEMPLATES_COLLECTION].find_one({"_id": camp["template_id"]}, {"name": 1, "uuid": 1})
                camp["template_info"] = template
            if camp.get("target_list_ids"):
                lists_info = []
                for list_id in camp["target_list_ids"]:
                    mlist = db[mailing_lists_db.MAILING_LISTS_COLLECTION].find_one({"_id": list_id}, {"name": 1, "uuid": 1})
                    if mlist: lists_info.append(mlist)
                camp["target_lists_info"] = lists_info

        serializer = CampaignOutputSerializer(campaigns_data, many=True)
        return Response(get_paginated_response_data(serializer.data, total_count, page, per_page))

    def post(self, request):
        serializer = CampaignInputSerializer(data=request.data)
        if serializer.is_valid():
            try:
                payload = serializer.validated_data.copy()
                if request.user and request.user.is_authenticated:
                    # Assuming user_id is stored as string (username or pk)
                    payload["created_by_user_id"] = str(request.user.username)

                campaign_doc = campaigns_db.create_campaign(payload)
                output_serializer = CampaignOutputSerializer(campaign_doc)
                return Response(output_serializer.data, status=status.HTTP_201_CREATED)
            except ValueError as ve:
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CampaignDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def _get_object_by_uuid_or_404(self, campaign_uuid, enrich=False):
        campaign = campaigns_db.get_campaign_by_uuid(campaign_uuid)
        if not campaign:
            raise Http404("Campaign not found.")
        if enrich: # Similar enrichment as in list view
            db = get_db()
            if campaign.get("template_id"):
                template = db[templates_db.TEMPLATES_COLLECTION].find_one({"_id": campaign["template_id"]}, {"name": 1, "uuid": 1})
                campaign["template_info"] = template
            if campaign.get("target_list_ids"):
                lists_info = []
                for list_id in campaign["target_list_ids"]:
                    mlist = db[mailing_lists_db.MAILING_LISTS_COLLECTION].find_one({"_id": list_id}, {"name": 1, "uuid": 1})
                    if mlist: lists_info.append(mlist)
                campaign["target_lists_info"] = lists_info
        return campaign

    def get(self, request, campaign_uuid):
        campaign = self._get_object_by_uuid_or_404(campaign_uuid, enrich=True)
        serializer = CampaignOutputSerializer(campaign)
        return Response(serializer.data)

    def put(self, request, campaign_uuid):
        self._get_object_by_uuid_or_404(campaign_uuid) # Check existence
        serializer = CampaignInputSerializer(data=request.data) # Full update
        if serializer.is_valid():
            try:
                modified_count = campaigns_db.update_campaign(campaign_uuid, serializer.validated_data)
                if modified_count > 0:
                    updated_campaign = self._get_object_by_uuid_or_404(campaign_uuid, enrich=True)
                    return Response(CampaignOutputSerializer(updated_campaign).data)
                return Response({"detail": "Campaign not found or no changes made."}, status=status.HTTP_404_NOT_FOUND)
            except ValueError as ve:
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, campaign_uuid):
        deleted_count = campaigns_db.delete_campaign(campaign_uuid)
        if deleted_count > 0:
            return Response(status=status.HTTP_204_NO_CONTENT)
        raise Http404("Campaign not found.")

# --- Campaign Actions ---
class CampaignStatusUpdateAPIView(APIView): # PUT /api/campaigns/{id}/status
    permission_classes = [permissions.IsAuthenticated]
    def put(self, request, campaign_uuid):
        campaign = campaigns_db.get_campaign_by_uuid(campaign_uuid)
        if not campaign: raise Http404

        serializer = CampaignStatusUpdateSerializer(data=request.data)
        if serializer.is_valid():
            new_status = serializer.validated_data['status']
            # TODO: Add Listmonk's status transition validation logic if complex
            modified_count = campaigns_db.update_campaign_status(campaign_uuid, new_status)
            if modified_count > 0:
                if new_status == "running": # Assuming "running" is the trigger
                    # tasks.process_campaign_sending_task.delay(str(campaign['_id'])) # Use ObjectId str
                    tasks.process_campaign_sending_task(str(campaign['_id'])) # Simulate for now

                updated_campaign = campaigns_db.get_campaign_by_uuid(campaign_uuid) # Re-fetch
                return Response(CampaignOutputSerializer(updated_campaign).data) # Return full campaign
            return Response({"detail": "Failed to update status or no change."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CampaignPreviewAPIView(APIView): # GET /api/campaigns/{id}/preview
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, campaign_uuid):
        campaign = campaigns_db.get_campaign_by_uuid(campaign_uuid)
        if not campaign: raise Http404
        # TODO: Actual template rendering with mock subscriber context
        return HttpResponse(campaign.get("body_html_source", ""), content_type="text/html")

class CampaignTestSendAPIView(APIView): # POST /api/campaigns/{id}/test
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, campaign_uuid):
        campaign = campaigns_db.get_campaign_by_uuid(campaign_uuid)
        if not campaign: raise Http404

        serializer = CampaignTestSendSerializer(data=request.data)
        if serializer.is_valid():
            emails_to_send = serializer.validated_data['emails']
            # TODO: Implement actual test sending logic (similar to single campaign send task but to arbitrary emails)
            # For now, simulate
            print(f"Simulating test send of campaign {campaign['name']} to: {emails_to_send}")
            # tasks.send_test_campaign_task.delay(str(campaign['_id']), emails_to_send)
            return Response({"data": True, "message": f"Test send initiated for {len(emails_to_send)} email(s)."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --- Public Subscription View (already somewhat defined, adjust if needed) ---
class PublicSubscriptionCreateAPIView(APIView): # POST /api/public/subscription
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = PublicSubscriptionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        email = data['email']
        name = data.get('name', email.split('@')[0])
        list_uuids_to_subscribe = data['list_uuids']

        try:
            # 1. Get or Create Subscriber
            subscriber_doc = subscribers_db.get_subscriber_by_email(email)
            if not subscriber_doc:
                subscriber_doc = subscribers_db.create_subscriber(email=email, name=name, status="enabled")
            elif subscriber_doc["name"] != name and name: # Update name if provided and different
                subscribers_db.update_subscriber(subscriber_doc["uuid"], {"name": name})
                subscriber_doc["name"] = name # Reflect update

            subscriber_obj_id = subscriber_doc["_id"]

            # 2. Subscribe to each list
            for list_uuid in list_uuids_to_subscribe:
                mlist = mailing_lists_db.get_mailing_list_by_uuid(list_uuid)
                if mlist and mlist.get("type") == "public":
                    list_obj_id = mlist["_id"]
                    sub_status = "confirmed"
                    if mlist.get("optin_type") == "double":
                        sub_status = "unconfirmed"
                        # tasks.send_optin_email_task.delay(str(subscriber_obj_id), str(list_obj_id)) # Use ObjectIds
                        tasks.send_optin_email_task(str(subscriber_obj_id), str(list_obj_id)) # Simulate

                    subscriptions_db.add_subscription(subscriber_obj_id, list_obj_id, sub_status)
                else:
                    print(f"Warning: Public list with UUID {list_uuid} not found or not public.")

            return Response({"data": True}, status=status.HTTP_200_OK) # Listmonk returns 200 OK

        except ValueError as ve: # e.g. subscriber creation failed due to pre-existing (should be caught by get_or_create logic)
             return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Public subscription error: {e}")
            return Response({"detail": "An unexpected error occurred during subscription."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# --- Tracking Views (already somewhat defined, adjust if needed) ---
from .db_access import tracking_events_db, links_db # Import new DALs

class TrackViewAPI(APIView): # GET /api/track/view/{camp_uuid}/{sub_uuid}/pixel.png
    authentication_classes = []
    permission_classes = []
    def get(self, request, campaign_uuid, subscriber_uuid, *args, **kwargs):
        user_agent = request.META.get('HTTP_USER_AGENT')
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        ip_address = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

        try:
            tracking_events_db.create_view_event(
                campaign_uuid=str(campaign_uuid), # Ensure UUIDs are passed as strings
                subscriber_uuid=str(subscriber_uuid),
                user_agent=user_agent,
                ip_address=ip_address
            )
        except Exception as e:
            print(f"Error recording view event: {e}. Camp: {campaign_uuid}, Sub: {subscriber_uuid}")
            # Do not fail pixel response

        pixel = Image.new('RGBA', (1, 1), (0, 0, 0, 0)) # Transparent
        response = HttpResponse(content_type="image/png")
        pixel.save(response, "PNG")
        return response


class TrackClickAPI(APIView): # GET /api/track/click/{camp_uuid}/{sub_uuid}/{link_uuid}/
    authentication_classes = []
    permission_classes = []
    def get(self, request, campaign_uuid, subscriber_uuid, link_uuid, *args, **kwargs):
        user_agent = request.META.get('HTTP_USER_AGENT')
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        ip_address = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

        redirect_url = "/" # Default fallback redirect
        try:
            link_document = links_db.get_link_by_uuid(str(link_uuid))

            if link_document and "url" in link_document:
                redirect_url = link_document["url"]
                tracking_events_db.create_click_event(
                    campaign_uuid=str(campaign_uuid),
                    subscriber_uuid=str(subscriber_uuid),
                    link_uuid=str(link_uuid), # Pass the original link's UUID
                    link_url=redirect_url,   # Pass the actual URL for denormalization/logging
                    user_agent=user_agent,
                    ip_address=ip_address
                )
            else:
                print(f"Link UUID {link_uuid} not found for click tracking.")

        except Exception as e:
            print(f"Error during link click tracking or link resolution: {e}")

        return HttpResponseRedirect(redirect_url)

class SubscriptionConfirmAPIView(APIView): # GET /api/subscriptions/confirm/{token}/
    authentication_classes = []
    permission_classes = []
    def get(self, request, token, *args, **kwargs):
        # Placeholder - actual logic needed
        print(f"Received subscription confirmation token: {token}")
        # Example:
        # valid_token, sub_obj_id_str, list_obj_id_str = tasks.validate_optin_token(token) # This task/util needs to exist
        # if valid_token:
        #     try:
        #         sub_obj_id = ObjectId(sub_obj_id_str)
        #         list_obj_id = ObjectId(list_obj_id_str)
        #         subscriptions_db.update_subscription_status(sub_obj_id, list_obj_id, "confirmed")
        #         # tasks.consume_optin_token(token) # Mark as used
        #         return HttpResponse("Subscription confirmed successfully!")
        #     except Exception as e:
        #         print(f"Error confirming subscription with token {token}: {e}")
        #         return HttpResponse("Error confirming subscription.", status=500)
        # else:
        #     return HttpResponse("Invalid or expired confirmation token.", status=400)
        return HttpResponse("Subscription confirmation endpoint hit (implement logic).", status=status.HTTP_501_NOT_IMPLEMENTED)


# TODO: Other specific Listmonk API endpoints (e.g., campaign analytics, more bulk subscriber ops)
# These would follow similar patterns: create serializer for request, APIView, call DAL, format response.
