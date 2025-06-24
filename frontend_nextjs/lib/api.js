// lib/api.js

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

// No more TypeScript interfaces here, but JSDoc can be used for type hinting if desired.
/**
 * @typedef {Object} Campaign
 * @property {string} _id - MongoDB ObjectId as string
 * @property {string} uuid
 * @property {string} name
 * @property {string} subject
 * @property {string} status
 * @property {string} created_at
 * @property {string} updated_at
 * @property {Array<{uuid: string, name: string}>} [target_lists_info] - Example if API returns enriched list info
 * @property {{to_send: number, sent: number, views: number, clicks: number}} [stats]
 */

/**
 * @typedef {Object} PaginatedResponse
 * @property {number} count
 * @property {string|null} next
 * @property {string|null} previous
 * @property {Campaign[]} results // Example for campaigns
 */

const getAuthHeaders = () => {
  // This is a placeholder. In a real app, you'd get the token from your auth system (e.g., NextAuth.js).
  const token = typeof window !== 'undefined' ? localStorage.getItem('authToken') : null;
  const headers = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Token ${token}`; // Assuming DRF Token Auth
  }
  return headers;
};

/**
 * @param {number} [page=1]
 * @param {number} [perPage=10]
 * @returns {Promise<PaginatedResponse>}
 */
export async function getCampaigns(page = 1, perPage = 10) {
  const response = await fetch(`${API_BASE_URL}/campaigns/?page=${page}&per_page=${perPage}`, {
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({})); // Try to get error detail
    throw new Error(errorData.detail || 'Failed to fetch campaigns');
  }
  return response.json();
}

/**
 * @param {string} uuid // Changed id to uuid to match APIView paths
 * @returns {Promise<Campaign>}
 */
export async function getCampaign(uuid) {
  const response = await fetch(`${API_BASE_URL}/campaigns/${uuid}/`, {
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch campaign ${uuid}`);
  }
  return response.json();
}

/**
 * @param {object} campaignData - Data for creating campaign (matching CampaignInputSerializer)
 * @returns {Promise<Campaign>}
 */
export async function createCampaign(campaignData) {
  const response = await fetch(`${API_BASE_URL}/campaigns/`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(campaignData),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to create campaign');
  }
  return response.json();
}

/**
 * @param {string} uuid
 * @param {object} campaignData - Data for updating campaign
 * @returns {Promise<Campaign>}
 */
export async function updateCampaign(uuid, campaignData) {
  const response = await fetch(`${API_BASE_URL}/campaigns/${uuid}/`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(campaignData),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to update campaign ${uuid}`);
  }
  return response.json();
}

/**
 * @param {string} uuid
 * @returns {Promise<void>}
 */
export async function deleteCampaign(uuid) {
  const response = await fetch(`${API_BASE_URL}/campaigns/${uuid}/`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!response.ok && response.status !== 204) { // 204 No Content is a success for DELETE
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to delete campaign ${uuid}`);
  }
}

/**
 * @typedef {Object} PublicSubscriptionPayload
 * @property {string} email
 * @property {string} [name]
 * @property {string[]} list_uuids
 */

/**
 * @param {PublicSubscriptionPayload} payload
 * @returns {Promise<{data: boolean}>}
 */
export async function publicSubscribe(payload) {
    const response = await fetch(`${API_BASE_URL}/public/subscription/`, { // Ensure this matches your urls.py
        method: 'POST',
        headers: { // No auth header for public endpoint
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Subscription failed');
    }
    return response.json();
}

/**
 * @param {string} uuid
 * @param {string} status
 * @returns {Promise<Campaign>}
 */
export async function updateCampaignStatus(uuid, newStatus) { // Renamed status to newStatus
    const response = await fetch(`${API_BASE_URL}/campaigns/${uuid}/status/`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({ status: newStatus }), // Ensure payload matches serializer
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to update status for campaign ${uuid}`);
    }
    return response.json();
}

// Add other API functions for subscribers, lists, templates as needed, using UUIDs for identifiers.
// Example:
// export async function getSubscribers(page = 1, perPage = 10, query = '') { /* ... */ }
// export async function createSubscriber(subscriberData) { /* ... */ }
// export async function getMailingLists(page = 1, perPage = 10) { /* ... */ }
// export async function createMailingList(listData) { /* ... */ }
// etc.
