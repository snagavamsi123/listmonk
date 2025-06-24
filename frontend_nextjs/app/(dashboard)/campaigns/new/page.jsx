// app/(dashboard)/campaigns/new/page.jsx
"use client";

import React, { useState } from 'react'; // Removed FormEvent as it's not used with manual preventDefault
import { useRouter } from 'next/navigation';
import { createCampaign } from '@/lib/api'; // Use .js extension

// No TypeScript interfaces, using JSDoc in api.js for CampaignFormData concept.

export default function NewCampaignPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    name: '',
    subject: '',
    from_email: '', // Consider fetching default from user settings or app config
    body_html_source: '', // Changed from 'body' to match MongoDB schema and CampaignInputSerializer
    content_type: 'html',
    campaign_type: 'regular',
    target_list_uuids: [], // Changed from target_list_ids to match CampaignInputSerializer
    template_uuid: null,   // Changed from template_id
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // TODO: In a real app, fetch lists and templates to populate select dropdowns dynamically.
  // Example:
  // const [availableLists, setAvailableLists] = useState([]);
  // useEffect(() => { async function loadData() { setAvailableLists(await getMailingLists()); } loadData(); }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleListSelection = (listUuid) => { // Changed to listUuid
    setFormData(prev => {
      const currentListUuids = prev.target_list_uuids || [];
      if (currentListUuids.includes(listUuid)) {
        return { ...prev, target_list_uuids: currentListUuids.filter(uuid => uuid !== listUuid) };
      } else {
        return { ...prev, target_list_uuids: [...currentListUuids, listUuid] };
      }
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault(); // Standard way to prevent default form submission
    setIsLoading(true);
    setError(null);

    if (!formData.name || !formData.subject || !formData.body_html_source) {
        setError("Name, subject, and body are required.");
        setIsLoading(false);
        return;
    }
    if (!formData.target_list_uuids || formData.target_list_uuids.length === 0) {
        setError("At least one target list must be selected.");
        setIsLoading(false);
        return;
    }

    try {
      // Ensure API payload matches CampaignInputSerializer expectations
      const payload = { ...formData };
      if (payload.template_uuid === null || payload.template_uuid === '') {
        delete payload.template_uuid; // Don't send null if it's optional and not selected
      }

      const newCampaign = await createCampaign(payload);
      router.push(`/campaigns/${newCampaign.uuid}`); // Use UUID from response
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  // UI/UX Note: Consistent form styling, clear labels, intuitive inputs, helpful error messages, loading states.
  // Tailwind classes provide the building blocks for this.

  return (
    <div className="container mx-auto p-4 md:p-6 lg:p-8">
      <div className="max-w-2xl mx-auto bg-white p-8 rounded-lg shadow-md">
        <h1 className="text-2xl font-semibold text-gray-800 mb-6">Create New Campaign</h1>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">Campaign Name</label>
            <input
              type="text" id="name" name="name" value={formData.name} onChange={handleChange} required
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            />
          </div>
          <div>
            <label htmlFor="subject" className="block text-sm font-medium text-gray-700 mb-1">Subject</label>
            <input
              type="text" id="subject" name="subject" value={formData.subject} onChange={handleChange} required
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            />
          </div>
          <div>
            <label htmlFor="from_email" className="block text-sm font-medium text-gray-700 mb-1">From Email</label>
            <input
              type="email" id="from_email" name="from_email" value={formData.from_email} onChange={handleChange} required
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              placeholder="sender@example.com"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label htmlFor="campaign_type" className="block text-sm font-medium text-gray-700 mb-1">Campaign Type</label>
              <select
                id="campaign_type" name="campaign_type" value={formData.campaign_type} onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              >
                <option value="regular">Regular</option>
                <option value="optin">Opt-in</option>
              </select>
            </div>
            <div>
              <label htmlFor="content_type" className="block text-sm font-medium text-gray-700 mb-1">Content Type</label>
              <select
                id="content_type" name="content_type" value={formData.content_type} onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              >
                <option value="html">HTML</option>
                <option value="richtext">Rich Text (implies HTML)</option>
                <option value="plain">Plain Text</option>
                {/* <option value="markdown">Markdown</option> */}
                {/* <option value="visual">Visual Builder (complex, needs specific editor)</option> */}
              </select>
            </div>
          </div>
          <div>
            <label htmlFor="body_html_source" className="block text-sm font-medium text-gray-700 mb-1">Body Content (HTML)</label>
            {/* UI/UX Note: For HTML/Rich Text, a proper editor (CKEditor, TinyMCE, Quill) is essential. */}
            <textarea
              id="body_html_source" name="body_html_source" value={formData.body_html_source} onChange={handleChange} rows={12} required
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              placeholder="Enter your HTML email content here..."
            />
          </div>

          {/* Placeholder for Target Lists - fetch and display dynamically */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Target Lists (Select at least one)</label>
            <div className="mt-2 space-y-2">
              {/* Example: Replace with actual fetched lists */}
              {[{uuid: 'mock-uuid-1', name: 'List Alpha'}, {uuid: 'mock-uuid-2', name: 'List Beta'}].map(list => (
                 <label key={list.uuid} className="flex items-center space-x-2 p-2 border rounded-md hover:bg-gray-50">
                    <input
                      type="checkbox"
                      checked={(formData.target_list_uuids || []).includes(list.uuid)}
                      onChange={() => handleListSelection(list.uuid)}
                      className="h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
                    />
                    <span className="text-sm text-gray-700">{list.name}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Placeholder for Template Selection - fetch and display dynamically */}
          <div>
            <label htmlFor="template_uuid" className="block text-sm font-medium text-gray-700 mb-1">Template (Optional)</label>
            <select
              id="template_uuid" name="template_uuid" value={formData.template_uuid || ''}
              onChange={e => setFormData({...formData, template_uuid: e.target.value || null})}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            >
              <option value="">No Template</option>
              {/* Example: <option value="template-uuid-1">My Awesome Template</option> */}
            </select>
          </div>

          {error && <p className="text-sm text-red-600 mt-2">{error}</p>}

          <div className="flex justify-end pt-2">
            <button
              type="button"
              onClick={() => router.back()}
              className="mr-3 px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-6 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
            >
              {isLoading ? 'Creating...' : 'Create Campaign'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
