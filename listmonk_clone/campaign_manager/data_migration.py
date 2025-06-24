import os
import django
import psycopg2 # For connecting to Listmonk DB
import psycopg2.extras
import uuid # For handling UUIDs

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listmonk_clone.listmonk_clone.settings')
django.setup()

from campaign_manager.models import (
    Subscriber, MailingList, Subscription, EmailTemplate, Campaign,
    CampaignListMembership, Link, LinkClick, CampaignView, MediaAsset,
    CampaignMediaAsset, Bounce,
    # Import Enums if direct string comparison/validation is needed, though models handle choices
    ListType, ListOptin, SubscriberStatus, SubscriptionStatus, CampaignStatus,
    CampaignType, ContentType, BounceType, TemplateType
)

# --- Configuration for Listmonk Source Database ---
# Replace with your actual Listmonk DB connection details
LISTMONK_DB_CONFIG = {
    'dbname': 'listmonk_source_db_name',
    'user': 'listmonk_source_user',
    'password': 'listmonk_source_password',
    'host': 'localhost', # Or your Listmonk DB host
    'port': '5432',
}

def get_listmonk_db_connection():
    return psycopg2.connect(**LISTMONK_DB_CONFIG)

def migrate_subscribers(conn):
    print("Starting subscriber migration...")
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT id, uuid, email, name, attribs, status, created_at, updated_at FROM subscribers")
        migrated_count = 0
        skipped_count = 0
        for row in cur:
            try:
                # Check if subscriber with this email or UUID already exists to avoid duplicates
                # if Subscriber.objects.filter(email=row['email']).exists() or \
                #    Subscriber.objects.filter(uuid=row['uuid']).exists():
                #     print(f"Skipping existing subscriber: {row['email']}")
                #     skipped_count += 1
                #     continue

                # Map status string (it should match Django choices value)
                status_val = row['status']
                if status_val not in SubscriberStatus.values:
                    print(f"Warning: Unknown subscriber status '{status_val}' for {row['email']}. Defaulting to ENABLED.")
                    status_val = SubscriberStatus.ENABLED

                sub, created = Subscriber.objects.update_or_create(
                    uuid=row['uuid'], # Use UUID as the primary lookup for idempotency
                    defaults={
                        'email': row['email'].lower(), # Ensure email is lowercase
                        'name': row['name'],
                        'attribs': row['attribs'] if row['attribs'] else {},
                        'status': status_val,
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at'],
                        # 'id': row['id'] # If you want to try to preserve original IDs, but ensure your model's PK allows it (not auto-incrementing in the same way)
                                        # Generally safer to let Django assign new PKs and map old IDs if needed.
                    }
                )
                if created:
                    migrated_count += 1
                else:
                    print(f"Updated existing subscriber: {row['email']}")
                    # skipped_count +=1 # Or count as updated
            except Exception as e:
                print(f"Error migrating subscriber {row['email']}: {e}")
        print(f"Subscribers migrated: {migrated_count}, skipped/updated: {skipped_count}")

def migrate_mailing_lists(conn):
    print("Starting mailing list migration...")
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT id, uuid, name, type, optin, tags, description, created_at, updated_at FROM lists")
        migrated_count = 0
        skipped_count = 0
        for row in cur:
            try:
                # if MailingList.objects.filter(uuid=row['uuid']).exists():
                #     print(f"Skipping existing mailing list: {row['name']}")
                #     skipped_count += 1
                #     continue

                list_type_val = row['type']
                if list_type_val not in ListType.values:
                    print(f"Warning: Unknown list type '{list_type_val}' for {row['name']}. Defaulting to PUBLIC.")
                    list_type_val = ListType.PUBLIC

                optin_val = row['optin']
                if optin_val not in ListOptin.values:
                    print(f"Warning: Unknown optin type '{optin_val}' for {row['name']}. Defaulting to SINGLE.")
                    optin_val = ListOptin.SINGLE

                mlist, created = MailingList.objects.update_or_create(
                    uuid=row['uuid'],
                    defaults={
                        'name': row['name'],
                        'list_type': list_type_val, # 'type' in source, 'list_type' in Django model
                        'optin': optin_val,
                        'tags': row['tags'] if row['tags'] else [], # Ensure it's a list for JSONField
                        'description': row['description'] if row['description'] else '',
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at'],
                    }
                )
                if created:
                    migrated_count += 1
                else:
                    # skipped_count +=1
                    print(f"Updated existing mailing list: {row['name']}")

            except Exception as e:
                print(f"Error migrating mailing list {row['name']}: {e}")
        print(f"Mailing lists migrated: {migrated_count}, skipped/updated: {skipped_count}")


def migrate_subscriptions(conn):
    print("Starting subscriptions migration...")
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        # Fetch original subscriber and list IDs from source for mapping
        cur.execute("""
            SELECT sl.subscriber_id as lm_subscriber_id,
                   sl.list_id as lm_list_id,
                   s.uuid as subscriber_uuid,
                   l.uuid as list_uuid,
                   sl.meta, sl.status, sl.created_at, sl.updated_at
            FROM subscriber_lists sl
            JOIN subscribers s ON sl.subscriber_id = s.id
            JOIN lists l ON sl.list_id = l.id
        """)
        migrated_count = 0
        skipped_count = 0
        for row in cur:
            try:
                subscriber = Subscriber.objects.get(uuid=row['subscriber_uuid'])
                mailing_list = MailingList.objects.get(uuid=row['list_uuid'])

                status_val = row['status']
                if status_val not in SubscriptionStatus.values:
                    print(f"Warning: Unknown subscription status '{status_val}'. Defaulting to UNCONFIRMED.")
                    status_val = SubscriptionStatus.UNCONFIRMED

                sub, created = Subscription.objects.update_or_create(
                    subscriber=subscriber,
                    mailing_list=mailing_list,
                    defaults={
                        'meta': row['meta'] if row['meta'] else {},
                        'status': status_val,
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at'],
                    }
                )
                if created:
                    migrated_count += 1
                else:
                    # skipped_count += 1
                    print(f"Updated existing subscription for {subscriber.email} to {mailing_list.name}")
            except Subscriber.DoesNotExist:
                print(f"Error migrating subscription: Subscriber with UUID {row['subscriber_uuid']} not found in target DB.")
                skipped_count += 1
            except MailingList.DoesNotExist:
                print(f"Error migrating subscription: MailingList with UUID {row['list_uuid']} not found in target DB.")
                skipped_count += 1
            except Exception as e:
                print(f"Error migrating subscription for Listmonk sub_id {row['lm_subscriber_id']}, list_id {row['lm_list_id']}: {e}")
                skipped_count += 1
        print(f"Subscriptions migrated: {migrated_count}, skipped: {skipped_count}")

def migrate_email_templates(conn):
    print("Starting email template migration...")
    # Similar logic to subscribers and lists
    # Map 'type' to 'template_type'
    # Handle 'is_default' carefully (ensure only one default per type if that's the logic)
    # ...
    print("Email template migration SKIPPED (placeholder).")


def migrate_campaigns(conn):
    print("Starting campaign migration...")
    # This is more complex due to FKs to templates, and M2M to lists via campaign_lists
    # 1. Migrate campaigns basic data
    # 2. Then migrate campaign_lists (CampaignListMembership)
    # Map 'type' to 'campaign_type'
    # Map 'template_id' by finding EmailTemplate via old ID or a new mapping table.
    # Map 'archive_template_id' similarly.
    # ...
    print("Campaign migration SKIPPED (placeholder).")

# ... Add functions for other models:
# migrate_campaign_list_memberships(conn)
# migrate_links(conn)
# migrate_link_clicks(conn)
# migrate_campaign_views(conn)
# migrate_media_assets(conn)
# migrate_campaign_media_assets(conn)
# migrate_bounces(conn)


def main():
    print("Starting Listmonk data migration...")
    try:
        conn = get_listmonk_db_connection()
        print("Successfully connected to Listmonk source database.")

        # Migrate in order of dependency
        migrate_email_templates(conn) # Templates first as campaigns might reference them
        migrate_subscribers(conn)
        migrate_mailing_lists(conn)
        migrate_subscriptions(conn)   # After subscribers and lists

        migrate_campaigns(conn)       # After templates and lists
        # migrate_campaign_list_memberships(conn) # After campaigns and lists

        # migrate_links(conn)
        # migrate_link_clicks(conn)     # After campaigns, subscribers, links
        # migrate_campaign_views(conn)  # After campaigns, subscribers

        # migrate_media_assets(conn)
        # migrate_campaign_media_assets(conn) # After campaigns, media_assets

        # migrate_bounces(conn)         # After subscribers, campaigns

        print("Data migration process completed.")

    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during migration: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("Listmonk source database connection closed.")

if __name__ == '__main__':
    # IMPORTANT:
    # This script is a placeholder and needs significant refinement.
    # 1. Backup both your source and target databases before running any migration.
    # 2. Test thoroughly in a development environment.
    # 3. Adjust field mappings, data transformations, and error handling as needed.
    # 4. Consider batching for large datasets to manage memory and transaction size.
    # 5. For foreign keys (e.g., template_id in campaigns), you'll need to map
    #    old Listmonk IDs to new Django IDs if you're not preserving original IDs
    #    or if original IDs might clash. Using UUIDs as the primary link (as done
    #    for subscriber and list in subscriptions migration) is a good approach.

    # To run this script:
    # Ensure your Django settings are configured, especially the database for the new app.
    # Ensure psycopg2 is installed in your Django environment.
    # Execute from the root of your Django project: python campaign_manager/data_migration.py
    print("Data migration script invoked. Ensure Django environment is set up and DBs are backed up.")
    # main() # Uncomment to run when ready, after careful review and setup.
    print("Migration run commented out by default. Review and uncomment main() to execute.")
