from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from unittest import mock # For mocking DAL calls
from bson import ObjectId # For constructing mock DB responses
from datetime import datetime
import uuid as py_uuid

# Assuming your serializers are in campaign_manager.serializers
from .serializers import (
    SubscriberInputSerializer, SubscriberOutputSerializer,
    CampaignInputSerializer, CampaignOutputSerializer,
    PublicSubscriptionRequestSerializer
)

User = get_user_model()

# Conceptual: If using mongomock, you'd import and patch the get_db client
# from mongomock import MongoClient
# @mock.patch('listmonk_clone.listmonk_clone.mongo_client.get_mongo_client', return_value=MongoClient())


class SubscriberAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='apiuser', password='password123')
        self.client.force_authenticate(user=self.user) # Use force_authenticate for DRF tests

        # Mock subscriber document structure that DAL would return
        self.mock_subscriber_doc = {
            "_id": ObjectId(),
            "uuid": str(py_uuid.uuid4()),
            "email": "test@example.com",
            "name": "Test User",
            "attribs": {},
            "status": "enabled",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        self.list_url = reverse('subscriber-list-create') # Ensure this name matches your urls.py

    @mock.patch('listmonk_clone.campaign_manager.db_access.subscribers_db.get_subscribers')
    def test_get_subscribers_list(self, mock_get_subscribers):
        # Setup mock DAL response
        mock_get_subscribers.return_value = ([self.mock_subscriber_doc], 1)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['email'], self.mock_subscriber_doc['email'])
        mock_get_subscribers.assert_called_once()

    @mock.patch('listmonk_clone.campaign_manager.db_access.subscribers_db.create_subscriber')
    def test_create_subscriber(self, mock_create_subscriber):
        new_sub_data = {'email': 'new@example.com', 'name': 'New Sub', 'status': 'enabled', "attribs": {}}

        # Mock DAL response after creation
        created_doc = {**new_sub_data, "_id": ObjectId(), "uuid": str(py_uuid.uuid4()),
                       "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()}
        mock_create_subscriber.return_value = created_doc

        response = self.client.post(self.list_url, new_sub_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], new_sub_data['email'])
        mock_create_subscriber.assert_called_once_with(
            email=new_sub_data['email'],
            name=new_sub_data['name'],
            status=new_sub_data['status'],
            attribs=new_sub_data['attribs']
        )

    @mock.patch('listmonk_clone.campaign_manager.db_access.subscribers_db.get_subscriber_by_uuid')
    def test_get_subscriber_detail(self, mock_get_subscriber_by_uuid):
        mock_get_subscriber_by_uuid.return_value = self.mock_subscriber_doc
        detail_url = reverse('subscriber-detail', kwargs={'subscriber_uuid': self.mock_subscriber_doc['uuid']})

        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['uuid'], self.mock_subscriber_doc['uuid'])
        mock_get_subscriber_by_uuid.assert_called_once_with(self.mock_subscriber_doc['uuid'])

    @mock.patch('listmonk_clone.campaign_manager.db_access.subscribers_db.update_subscriber')
    @mock.patch('listmonk_clone.campaign_manager.db_access.subscribers_db.get_subscriber_by_uuid')
    def test_update_subscriber(self, mock_get_subscriber_by_uuid, mock_update_subscriber):
        update_data = {'name': 'Updated Name', 'status': 'disabled'}

        # Mock get_subscriber_by_uuid for the _get_object_by_uuid_or_404 check in the view
        mock_get_subscriber_by_uuid.side_effect = [
            self.mock_subscriber_doc, # First call for existence check
            {**self.mock_subscriber_doc, **update_data, "updated_at": datetime.utcnow()} # Second call to return updated doc
        ]
        mock_update_subscriber.return_value = 1 # Simulate 1 document modified

        detail_url = reverse('subscriber-detail', kwargs={'subscriber_uuid': self.mock_subscriber_doc['uuid']})
        response = self.client.put(detail_url, update_data, format='json') # PUT requires all fields in serializer if not partial

        # To make PUT work with partial data for test, we need to pass all required fields of SubscriberInputSerializer
        # or the serializer should handle partial updates gracefully for PUT if that's the design.
        # For this test, let's assume the view's serializer for PUT/PATCH is SubscriberInputSerializer.
        # The input serializer requires email, name, status.
        full_update_data = {
            'email': self.mock_subscriber_doc['email'], # Provide existing email
            'name': update_data['name'],
            'status': update_data['status'],
            'attribs': self.mock_subscriber_doc['attribs']
        }

        response = self.client.put(detail_url, full_update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], update_data['name'])
        mock_update_subscriber.assert_called_once_with(self.mock_subscriber_doc['uuid'], full_update_data)


    @mock.patch('listmonk_clone.campaign_manager.db_access.subscribers_db.delete_subscriber')
    def test_delete_subscriber(self, mock_delete_subscriber):
        mock_delete_subscriber.return_value = 1 # Simulate 1 document deleted
        detail_url = reverse('subscriber-detail', kwargs={'subscriber_uuid': self.mock_subscriber_doc['uuid']})

        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        mock_delete_subscriber.assert_called_once_with(self.mock_subscriber_doc['uuid'])


class CampaignAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='campaignuser', password='password123')
        self.client.force_authenticate(user=self.user)

        self.list_uuid = str(py_uuid.uuid4())
        self.template_uuid = str(py_uuid.uuid4())

        self.create_url = reverse('campaign-list-create')
        self.campaign_payload = {
            'name': 'Test API Campaign',
            'subject': 'Test Subject',
            'from_email': 'test@sender.com',
            'body_html_source': '<p>Hello World</p>',
            'content_type': 'html',
            'campaign_type': 'regular',
            'target_list_uuids': [self.list_uuid],
            'template_uuid': self.template_uuid,
        }

    @mock.patch('listmonk_clone.campaign_manager.db_access.campaigns_db.create_campaign')
    def test_create_campaign(self, mock_create_campaign):
        # Mock the DAL response for create_campaign
        mock_campaign_doc = {
            "_id": ObjectId(),
            "uuid": str(py_uuid.uuid4()),
            **self.campaign_payload,
            "created_by_user_id": self.user.username, # Assuming username is stored
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "stats": {"to_send":0, "sent":0, "views":0, "clicks":0, "failed":0, "bounces":0, "unsubscribes":0}, # default stats
            "template_id": ObjectId(), # DAL would have resolved template_uuid to ObjectId
            "target_list_ids": [ObjectId()] # DAL would have resolved list_uuids to ObjectIds
        }
        mock_create_campaign.return_value = mock_campaign_doc

        response = self.client.post(self.create_url, self.campaign_payload, format='json')

        if response.status_code != status.HTTP_201_CREATED:
            print("Create Campaign API Error:", response.data) # Debug output

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], self.campaign_payload['name'])
        self.assertEqual(response.data['created_by_user_id'], self.user.username)

        # Assert that the DAL function was called with the payload + user
        expected_dal_payload = {**self.campaign_payload, "created_by_user_id": self.user.username}
        mock_create_campaign.assert_called_once_with(expected_dal_payload)


    @mock.patch('listmonk_clone.campaign_manager.db_access.campaigns_db.get_campaign_by_uuid')
    @mock.patch('listmonk_clone.campaign_manager.db_access.campaigns_db.update_campaign_status')
    @mock.patch('listmonk_clone.campaign_manager.tasks.process_campaign_sending_task') # Mock Celery task
    def test_update_campaign_status_to_running(self, mock_process_task, mock_update_status, mock_get_campaign):
        campaign_uuid = str(py_uuid.uuid4())
        mock_campaign_doc = {"_id": ObjectId(), "uuid": campaign_uuid, "name": "Test Camp"} # Min data for view

        mock_get_campaign.return_value = mock_campaign_doc # For initial fetch in view
        mock_update_status.return_value = 1 # Simulate update success

        # Mock the re-fetch after status update
        # Need to ensure this mock_get_campaign call happens *after* the update
        # A more robust way is to have the update_campaign_status DAL return the updated doc.
        # For simplicity, we assume the view re-fetches.
        mock_get_campaign.side_effect = [
            mock_campaign_doc, # First call in view
            {**mock_campaign_doc, "status": "running", "updated_at": datetime.utcnow()} # Second call (re-fetch)
        ]

        url = reverse('campaign-update-status', kwargs={'campaign_uuid': campaign_uuid})
        response = self.client.put(url, {'status': 'running'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'running')
        mock_update_status.assert_called_once_with(campaign_uuid, 'running')
        mock_process_task.assert_called_once_with(str(mock_campaign_doc['_id']))


# --- DAL Unit Tests (Conceptual - would use mongomock or a test DB) ---
# These tests would directly call your DAL functions.

# Example using mongomock (conceptual, assuming mongomock is installed and configured)
# from mongomock import MongoClient
# from listmonk_clone.listmonk_clone import mongo_client as mc_module # Module where get_db is
# from listmonk_clone.campaign_manager.db_access import subscribers_db as s_db

# class SubscriberDALTests(TestCase):
#     def setUp(self):
#         self.mock_mongo_client = MongoClient()
#         # Patch the get_db function in your mongo_client module to return a mongomock DB
#         self.get_db_patcher = mock.patch.object(mc_module, 'get_db', return_value=self.mock_mongo_client.test_db)
#         self.mock_get_db = self.get_db_patcher.start()
#         self.addCleanup(self.get_db_patcher.stop) # Ensure patch is stopped after test

#         self.subscribers_collection = self.mock_get_db()[s_db.SUBSCRIBERS_COLLECTION]

#     def test_dal_create_subscriber(self):
#         data = {'email': 'dal@example.com', 'name': 'DAL Test', 'status': 'enabled', 'attribs': {}}
#         created_doc = s_db.create_subscriber(**data)

#         self.assertIsNotNone(created_doc['_id'])
#         self.assertEqual(created_doc['email'], data['email'])

#         # Verify it's in the mock DB
#         db_doc = self.subscribers_collection.find_one({"email": data['email']})
#         self.assertIsNotNone(db_doc)
#         self.assertEqual(db_doc['name'], data['name'])

#     def test_dal_create_subscriber_duplicate_email(self):
#         data = {'email': 'dal_dup@example.com', 'name': 'DAL Dup1', 'status': 'enabled', 'attribs': {}}
#         s_db.create_subscriber(**data)
#         with self.assertRaises(ValueError): # As per create_subscriber logic
#             s_db.create_subscriber(email='dal_dup@example.com', name='DAL Dup2')


# --- Celery Task Tests (Conceptual) ---
# from unittest.mock import patch
# from listmonk_clone.campaign_manager import tasks

# class CampaignCeleryTaskTests(TestCase):
#     @patch('listmonk_clone.campaign_manager.db_access.campaigns_db.get_campaign_by_id')
#     @patch('listmonk_clone.campaign_manager.db_access.subscriptions_db.get_subscribers_for_list')
#     @patch('listmonk_clone.campaign_manager.db_access.subscribers_db.get_subscriber_by_id') # if sub-task fetches individually
#     @patch('listmonk_clone.campaign_manager.tasks.send_email_to_subscriber_batch_task.delay')
#     def test_process_campaign_sending_task_dispatches_batches(self, mock_batch_task_delay, mock_get_sub_by_id, mock_get_subs_for_list, mock_get_camp_by_id):
#         campaign_id_str = str(ObjectId())
#         mock_get_camp_by_id.return_value = {
#             "_id": ObjectId(campaign_id_str), "uuid": "camp-uuid", "name": "Test Campaign",
#             "status": "running", "target_list_ids": [ObjectId(), ObjectId()]
#         }
#         # Mock get_subscribers_for_list to return some subscriber ObjectIds
#         # This needs to return a tuple: (list_of_ids, total_count)
#         mock_get_subs_for_list.return_value = ([ObjectId() for _ in range(tasks.SUBSCRIBER_BATCH_SIZE * 2 + 50)], tasks.SUBSCRIBER_BATCH_SIZE * 2 + 50)

#         # Mock subscriber status check if process_campaign_sending_task does that
#         # (The current tasks.py version does this)
#         mock_sub_collection = mock.Mock()
#         mock_sub_collection.find.return_value = [{"_id": sub_id} for sub_id in mock_get_subs_for_list.return_value[0]] # Simulate all are enabled

#         with mock.patch('listmonk_clone.campaign_manager.db_access.subscribers_db._get_collection', return_value=mock_sub_collection):
#             tasks.process_campaign_sending_task(campaign_id_str)

#         self.assertTrue(mock_batch_task_delay.call_count >= 3) # Should be 3 batches for this many subs
#         # Further assertions on arguments passed to mock_batch_task_delay

#     @patch('listmonk_clone.campaign_manager.db_access.campaigns_db.get_campaign_by_id')
#     @patch('listmonk_clone.campaign_manager.db_access.subscribers_db.get_subscriber_by_id')
#     @patch('listmonk_clone.campaign_manager.tasks.render_email_content') # Mock rendering
#     @patch('listmonk_clone.campaign_manager.tasks.send_mail') # Mock actual email sending
#     @patch('listmonk_clone.campaign_manager.db_access.campaigns_db.update_campaign_stats')
#     def test_send_email_to_subscriber_batch_task(self, mock_update_stats, mock_send_mail, mock_render_content, mock_get_sub, mock_get_camp):
#         campaign_id_str = str(ObjectId())
#         sub_ids_strs = [str(ObjectId()), str(ObjectId())]

#         mock_get_camp.return_value = {"_id": ObjectId(campaign_id_str), "uuid": "camp-uuid", "name": "Batch Test", "subject": "Hi", "from_email": "b@b.com", "body_html_source": "Body {{Subscriber.Name}}"}
#         mock_get_sub.side_effect = [
#             {"_id": ObjectId(sub_ids_strs[0]), "uuid": "sub-uuid-1", "email": "s1@ex.com", "name": "S1", "status": "enabled"},
#             {"_id": ObjectId(sub_ids_strs[1]), "uuid": "sub-uuid-2", "email": "s2@ex.com", "name": "S2", "status": "enabled"}
#         ]
#         mock_render_content.return_value = ("Rendered Subject", "<p>Rendered Body</p>")

#         tasks.send_email_to_subscriber_batch_task(campaign_id_str, sub_ids_strs)

#         self.assertEqual(mock_send_mail.call_count, 2)
#         self.assertEqual(mock_update_stats.call_count, 1) # One call for successful_sends
#         # Check if update_stats was called with correct increment
#         mock_update_stats.assert_called_with(mock_get_camp.return_value["uuid"], {"$inc": {"stats.sent": 2}})
```

**Explanation of Changes and Testing Strategy:**

1.  **Removed ORM Model Tests:** Tests like `SubscriberModelTests` that directly used Django ORM's `objects.create()` are removed for `campaign_manager` entities.
2.  **API Tests (`APITestCase`):**
    *   These are kept but heavily modified.
    *   **Mocking the DAL:** The core change is to mock the DAL functions (e.g., `subscribers_db.get_subscribers`, `campaigns_db.create_campaign`) using `unittest.mock.patch`.
    *   **Focus:** Tests now verify that:
        *   The APIView correctly parses request data (validated by serializers).
        *   The correct DAL function is called with the expected arguments.
        *   The response from the APIView matches the expected structure and data, based on what the mocked DAL function returns.
        *   Authentication and permissions (conceptually, `force_authenticate` is used).
    *   **URL Naming:** Uses `reverse()` with URL names (e.g., `subscriber-list-create`, `campaign-detail`). These names must match what's defined in `campaign_manager/urls.py`.
    *   **Data:** Test data (`self.mock_subscriber_doc`) simulates what a Pymongo query might return (including `_id` as `ObjectId`).
3.  **DAL Unit Tests (Conceptual):**
    *   A new section is commented out, outlining how DAL functions themselves would be tested.
    *   This would involve using `mongomock` (a library that simulates MongoDB in memory) or connecting to a real test MongoDB instance.
    *   The example shows patching `mongo_client.get_db` to return a `mongomock` database, then testing a DAL function like `subscribers_db.create_subscriber` by checking its effect on the mock database.
4.  **Celery Task Tests (Conceptual):**
    *   Also outlined conceptually.
    *   These tests would mock the DAL functions and any external services (like `send_mail`).
    *   Focus on testing the logic within the task and ensuring sub-tasks are dispatched correctly (e.g., `process_campaign_sending_task` dispatching `send_email_to_subscriber_batch_task`).
    *   The example for `test_process_campaign_sending_task_dispatches_batches` shows mocking the sub-task's `.delay()` method.
    *   The example for `test_send_email_to_subscriber_batch_task` shows mocking `send_mail` and `render_email_content` to test if the email sending part behaves as expected.

This refactoring provides a testing structure appropriate for the Pymongo-based architecture, emphasizing mocking the data layer for API tests and outlining how the data layer itself and asynchronous tasks would be tested.
