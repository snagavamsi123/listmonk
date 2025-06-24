# campaign_manager/tasks.py
# from celery import shared_task # Assuming Celery is set up
from django.utils import timezone
# from django.template import Template, Context # Using basic string formatting for now for Mongo data
from django.core.mail import send_mail # Or a more robust email sending library
from django.conf import settings
from bson import ObjectId
import uuid # For generating tokens

# Import DAL modules
from .db_access import campaigns_db, subscribers_db, templates_db, subscriptions_db, tracking_events_db # Assume tracking_events_db exists

# Placeholder for a decorator if not using @shared_task
def shared_task(func):
    def wrapper(*args, **kwargs):
        print(f"CELERY TASK (simulated): {func.__name__} called with args={args} kwargs={kwargs}")
        try:
            return func(*args, **kwargs) # Simulate execution
        except Exception as e:
            print(f"Error in task {func.__name__}: {e}")
            # Add proper error handling/retry logic for Celery here
            raise
    return wrapper


# --- Constants ---
SUBSCRIBER_BATCH_SIZE = getattr(settings, 'CELERY_SUBSCRIBER_BATCH_SIZE', 500) # How many subscribers to process in one sub-task

# --- Email Rendering Helper (Conceptual) ---
def render_email_content(template_content: str, campaign_content: str, subscriber_data: dict, campaign_data: dict) -> tuple[str, str]:
    """
    Renders email subject and body.
    - template_content: HTML structure of the email template.
    - campaign_content: Specific content for this campaign (HTML).
    - subscriber_data: Dictionary of subscriber details.
    - campaign_data: Dictionary of campaign details.

    Returns (rendered_subject, rendered_html_body)
    This is highly simplified. A real template engine (like Jinja2 if not using Django's)
    would be more robust for complex substitutions and logic.
    """
    # Simple placeholder replacement. {{ Subscriber.Email }}, {{ Campaign.Name }} etc.
    # This assumes campaign_content is the primary body, and template_content might wrap it.
    # Or, template_content has a placeholder like {{ content }} for campaign_content.

    # For subject:
    subject = campaign_data.get("subject", "Your Newsletter")
    subject = subject.replace("{{Subscriber.Name}}", subscriber_data.get("name", ""))
    subject = subject.replace("{{Subscriber.Email}}", subscriber_data.get("email", ""))
    # Add more replacements as needed

    # For body:
    # Assume campaign_data['body_html_source'] is the main content.
    # A template might have {{ main_content }} which gets replaced by campaign_data['body_html_source'].
    # For now, let's assume campaign_data['body_html_source'] is the full body to be personalized.

    body = campaign_data.get("body_html_source", "<p>No content.</p>")
    body = body.replace("{{Subscriber.Name}}", subscriber_data.get("name", ""))
    body = body.replace("{{Subscriber.Email}}", subscriber_data.get("email", ""))
    body = body.replace("{{Subscriber.UUID}}", subscriber_data.get("uuid", ""))
    body = body.replace("{{Campaign.UUID}}", campaign_data.get("uuid", ""))
    body = body.replace("{{Campaign.Name}}", campaign_data.get("name", ""))

    # TODO: Add Unsubscribe Link
    # unsubscribe_link = f"{settings.FRONTEND_URL}/unsubscribe/{subscriber_data.get('uuid')}/?campaign_uuid={campaign_data.get('uuid')}"
    # body = body.replace("{{UnsubscribeURL}}", unsubscribe_link)

    # TODO: Add View in Browser Link
    # view_in_browser_link = f"{settings.FRONTEND_URL}/campaigns/view/{campaign_data.get('uuid')}/?subscriber_uuid={subscriber_data.get('uuid')}"
    # body = body.replace("{{ViewInBrowserURL}}", view_in_browser_link)

    # TODO: Tracking Pixel
    # tracking_pixel_url = generate_tracking_pixel_url(campaign_data, subscriber_data) # from previous tasks.py
    # body += f'<img src="{tracking_pixel_url}" width="1" height="1" alt="" />'

    # TODO: Link Tracking (replace links in `body`)
    # body = replace_links_for_tracking(body, campaign_data, subscriber_data)

    return subject, body


# --- Campaign Sending Tasks ---
@shared_task
def send_email_to_subscriber_batch_task(campaign_object_id_str: str, subscriber_object_ids_strs: list[str]):
    """
    Sends campaign email to a batch of subscribers.
    """
    campaign_doc = campaigns_db.get_campaign_by_id(campaign_object_id_str)
    if not campaign_doc:
        print(f"Campaign ObjectId {campaign_object_id_str} not found. Aborting batch.")
        return

    # Fetch template content if campaign uses one
    template_content = ""
    if campaign_doc.get("template_id"):
        template_doc = templates_db.get_template_by_id(str(campaign_doc["template_id"]))
        if template_doc:
            template_content = template_doc.get("body_html", "")
        else:
            print(f"Warning: Template ID {campaign_doc['template_id']} not found for campaign {campaign_doc['name']}.")

    successful_sends = 0
    failed_sends = 0

    # Fetch subscriber details in a batch if possible, or one by one
    # For this example, fetching one by one. In production, a bulk fetch would be better.
    for sub_id_str in subscriber_object_ids_strs:
        subscriber_doc = subscribers_db.get_subscriber_by_id(sub_id_str)
        if not subscriber_doc or subscriber_doc.get("status") != "enabled":
            print(f"Skipping subscriber ObjectId {sub_id_str} (not found or not enabled).")
            failed_sends +=1 # Count as failed for this batch if it was supposed to be sent
            continue

        try:
            subject, html_body = render_email_content(
                template_content=template_content,
                campaign_content=campaign_doc.get("body_html_source", ""),
                subscriber_data=subscriber_doc,
                campaign_data=campaign_doc
            )

            # Simulate sending email
            # send_mail(
            #     subject,
            #     "", # Plain text part - generate from HTML or use campaign.alt_body
            #     campaign_doc.get("from_email") or settings.DEFAULT_FROM_EMAIL,
            #     [subscriber_doc["email"]],
            #     html_message=html_body,
            # )
            print(f"SIMULATED EMAIL to {subscriber_doc['email']} for campaign '{campaign_doc['name']}'")
            successful_sends += 1
        except Exception as e:
            print(f"Error sending to {subscriber_doc.get('email', sub_id_str)}: {e}")
            failed_sends += 1
            # TODO: Log specific failure for potential retry or dead letter queue

    # Update campaign stats for this batch
    if successful_sends > 0:
        campaigns_db.update_campaign_stats(campaign_doc["uuid"], {"$inc": {"stats.sent": successful_sends}})
    if failed_sends > 0:
        campaigns_db.update_campaign_stats(campaign_doc["uuid"], {"$inc": {"stats.failed": failed_sends}})

    print(f"Batch for campaign {campaign_doc['name']} (ID: {campaign_object_id_str}): {successful_sends} sent, {failed_sends} failed.")


@shared_task
def process_campaign_sending_task(campaign_object_id_str: str):
    """
    Orchestrates sending a campaign. Fetches target subscribers and dispatches batch tasks.
    """
    campaign_doc = campaigns_db.get_campaign_by_id(campaign_object_id_str)
    if not campaign_doc:
        print(f"Campaign ObjectId {campaign_object_id_str} not found for sending.")
        return

    if campaign_doc.get("status") != "running":
        print(f"Campaign {campaign_doc['name']} is not 'running'. Status: {campaign_doc.get('status')}. Halting send.")
        return

    print(f"Processing campaign sending for: {campaign_doc['name']} (UUID: {campaign_doc['uuid']})")

    target_list_object_ids = campaign_doc.get("target_list_ids", [])
    if not target_list_object_ids:
        print(f"No target lists for campaign {campaign_doc['name']}. Marking as finished.")
        campaigns_db.update_campaign_status(campaign_doc["uuid"], "finished")
        campaigns_db.update_campaign_stats(campaign_doc["uuid"], {"$set": {"stats.to_send": 0}})
        return

    all_subscriber_object_ids_to_send = set()
    current_page = 1

    # TODO: This part needs to be highly optimized for millions of subscribers.
    # Fetching all subscriber IDs for all lists at once might be too much.
    # Consider processing list by list, or using MongoDB aggregation if possible
    # to get a distinct list of subscriber ObjectIds that are 'confirmed' and 'enabled'.

    for list_obj_id in target_list_object_ids:
        # Fetch confirmed and enabled subscribers for this list
        # This could be a very large set of IDs.
        # The DAL function `get_subscribers_for_list` should support pagination.
        # We need to iterate through pages for each list.

        # Simplified for now: get all relevant subscriber_ids for the list at once.
        # In reality, you'd paginate through subscriptions_db.get_subscribers_for_list

        # Get ObjectIds of subscribers who are 'confirmed' on this list
        confirmed_sub_ids, _ = subscriptions_db.get_subscribers_for_list(list_obj_id, status_filter="confirmed", per_page=10000000) # Large per_page for demo

        if confirmed_sub_ids:
            # Now check global status of these subscribers (must be 'enabled')
            # This requires fetching these subscribers from the 'subscribers' collection.
            # This is an N+M problem if not careful.
            # A better approach: get confirmed sub_ids, then do one bulk query to subscribers collection
            # to filter by status="enabled".

            # Example:
            enabled_globally_subs = subscribers_db._get_collection().find( # Accessing private method for brevity
                {"_id": {"$in": confirmed_sub_ids}, "status": "enabled"},
                {"_id": 1} # Only need their IDs
            )
            for sub_doc in enabled_globally_subs:
                all_subscriber_object_ids_to_send.add(str(sub_doc["_id"]))


    subscriber_ids_list = list(all_subscriber_object_ids_to_send)
    total_to_send = len(subscriber_ids_list)

    campaigns_db.update_campaign_stats(campaign_doc["uuid"], {"$set": {"stats.to_send": total_to_send, "stats.sent": 0, "stats.failed": 0}})
    print(f"Campaign '{campaign_doc['name']}' has {total_to_send} unique, confirmed, enabled subscribers to send to.")

    if total_to_send == 0:
        campaigns_db.update_campaign_status(campaign_doc["uuid"], "finished")
        print(f"No subscribers to send to for campaign {campaign_doc['name']}. Marking as finished.")
        return

    # Dispatch batch tasks
    for i in range(0, total_to_send, SUBSCRIBER_BATCH_SIZE):
        batch_ids_strs = subscriber_ids_list[i:i + SUBSCRIBER_BATCH_SIZE]
        # send_email_to_subscriber_batch_task.delay(campaign_object_id_str, batch_ids_strs) # Real Celery
        send_email_to_subscriber_batch_task(campaign_object_id_str, batch_ids_strs) # Simulate
        print(f"Dispatched batch {i//SUBSCRIBER_BATCH_SIZE + 1} for campaign {campaign_doc['name']}")

    # This task only dispatches. Actual 'finished' status might be set by a monitoring task
    # or after all batch tasks report completion. For simplicity here, we assume dispatch means it will finish.
    # A more robust system would track batch completions.
    # For now, let's assume it's effectively finished once all batches are dispatched.
    # Note: If a campaign is paused and resumed, this logic needs to handle not re-sending to already processed subscribers.
    # This requires storing send progress (e.g. last_processed_subscriber_id for each list or a set of sent subscriber_ids).

    # campaigns_db.update_campaign_status(campaign_doc["uuid"], "finished") # This might be premature.
    print(f"All batches dispatched for campaign '{campaign_doc['name']}'. Monitoring needed for actual completion.")


# --- Opt-in Email Task ---
@shared_task
def send_optin_email_task(subscriber_object_id_str: str, list_object_id_str: str):
    subscriber_doc = subscribers_db.get_subscriber_by_id(subscriber_object_id_str)
    list_doc = mailing_lists_db.get_mailing_list_by_id(list_object_id_str)

    if not subscriber_doc or not list_doc:
        print(f"Subscriber or List not found for opt-in email. Sub: {subscriber_object_id_str}, List: {list_object_id_str}")
        return

    # TODO: Generate a unique confirmation token (e.g., JWT or Django's signing mechanism)
    # Store token temporarily (e.g., in Redis with TTL, or a 'pending_confirmations' collection)
    # associated with subscriber_id and list_id.
    confirmation_token = f"confirm-token-{uuid.uuid4()}" # Highly insecure placeholder
    # confirmation_url = f"{settings.FRONTEND_URL}/confirm-subscription/?token={confirmation_token}"
    confirmation_url = f"http://localhost:3000/confirm-subscription/?token={confirmation_token}" # Example

    print(f"Simulating sending opt-in email to {subscriber_doc['email']} for list '{list_doc['name']}'.")
    print(f"Confirmation URL: {confirmation_url}")

    # subject = f"Confirm your subscription to {list_doc['name']}"
    # message_body = f"Please confirm your subscription by clicking here: {confirmation_url}"
    # try:
    #     send_mail(subject, message_body, settings.DEFAULT_FROM_EMAIL, [subscriber_doc['email']])
    # except Exception as e:
    #     print(f"Error sending opt-in email to {subscriber_doc['email']}: {e}")


# --- Tracking Event Recording (called by API views) ---
def record_campaign_view(campaign_uuid_str: str, subscriber_uuid_str: str, user_agent: str = None, ip_address: str = None):
    # This function would now use tracking_events_db.py
    # For now, direct print:
    print(f"EVENT RECORD (VIEW): Campaign UUID: {campaign_uuid_str}, Sub UUID: {subscriber_uuid_str}, UA: {user_agent}, IP: {ip_address}")
    # tracking_events_db.create_view_event(campaign_uuid_str, subscriber_uuid_str, user_agent, ip_address)
    return True # Assume success for now

def record_link_click(campaign_uuid_str: str, subscriber_uuid_str: str, link_uuid_str: str, link_url: str, user_agent: str = None, ip_address: str = None):
    # This function would now use tracking_events_db.py
    print(f"EVENT RECORD (CLICK): Camp UUID: {campaign_uuid_str}, Sub UUID: {subscriber_uuid_str}, Link UUID: {link_uuid_str}, URL: {link_url}, UA: {user_agent}, IP: {ip_address}")
    # tracking_events_db.create_click_event(campaign_uuid_str, subscriber_uuid_str, link_uuid_str, link_url, user_agent, ip_address)
    return True # Assume success for now


# --- Periodic task to aggregate stats (Example) ---
@shared_task
def aggregate_tracking_stats_task():
    """
    Periodically aggregates raw tracking events into campaign stats.
    This is a complex task that would query `tracking_events` and update `campaigns.stats`.
    """
    print("Simulating aggregation of tracking stats...")
    # 1. Find campaigns that have unprocessed tracking events.
    # 2. For each campaign:
    #    - Count new views from `tracking_events` for this campaign (where `processed_for_stats_at` is null).
    #    - Count new clicks similarly.
    #    - Update `campaigns.stats.views` and `campaigns.stats.clicks` using $inc.
    #    - Mark processed events in `tracking_events` (set `processed_for_stats_at`).
    # This needs to be done carefully to avoid race conditions and ensure atomicity if possible.
    pass
