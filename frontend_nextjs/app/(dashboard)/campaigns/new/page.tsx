// app/(dashboard)/campaigns/new/page.tsx
"use client";

import React, { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation'; // For App Router
import { createCampaign } from '@/lib/api'; // Assuming api.ts is in lib

// Define a type for the form state, can be more specific
interface CampaignFormData {
  name: string;
  subject: string;
  from_email: string;
  body: string;
  content_type: string; // 'html', 'richtext', 'plain' etc.
  campaign_type: string; // 'regular', 'optin'
  // Add 'target_list_ids' if you have lists data available for selection
  target_list_ids?: number[];
  template_id?: number | null;
  // Add other fields as required by your CampaignDetailSerializer for creation
}

export default function NewCampaignPage() {
  const router = useRouter();
  const [formData, setFormData] = useState<CampaignFormData>({
    name: '',
    subject: '',
    from_email: '', // Should probably default to a user/app setting
    body: '',
    content_type: 'html', // Default content type
    campaign_type: 'regular', // Default campaign type
    target_list_ids: [],
    template_id: null,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // In a real app, you'd fetch lists and templates to populate select dropdowns
  // For example:
  // const [lists, setLists] = useState([]);
  // useEffect(() => { async function loadLists() { ... setLists(await getLists()); } loadLists(); }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } {= e.target;}
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleListSelection = (listId: number) => {
    setFormData(prev => {
      const currentListIds = prev.target_list_ids || [];
      if (currentListIds.includes(listId)) {
        return { ...prev, target_list_ids: currentListIds.filter(id => id !== listId) };
      } else {
        return { ...prev, target_list_ids: [...currentListIds, listId] };
      }
    });
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    // Basic validation (add more as needed)
    if (!formData.name || !formData.subject || !formData.body) {
        setError("Name, subject, and body are required.");
        setIsLoading(false);
        return;
    }
    if (!formData.target_list_ids || formData.target_list_ids.length === 0) {
        setError("At least one target list must be selected.");
        setIsLoading(false);
        return;
    }


    try {
      const newCampaign = await createCampaign(formData);
      // Redirect to the new campaign's page or the campaigns list
      router.push(`/campaigns/${newCampaign.id}`); // Or router.push('/campaigns');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  // Basic form styling for readability
  const inputStyle = { display: 'block', marginBottom: '10px', padding: '8px', width: '300px' };
  const labelStyle = { display: 'block', marginBottom: '5px', fontWeight: 'bold' };

  return (
    <div style={{ padding: '20px' }}>
      <h1>Create New Campaign</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="name" style={labelStyle}>Campaign Name:</label>
          <input type="text" id="name" name="name" value={formData.name} onChange={handleChange} required style={inputStyle} />
        </div>
        <div>
          <label htmlFor="subject" style={labelStyle}>Subject:</label>
          <input type="text" id="subject" name="subject" value={formData.subject} onChange={handleChange} required style={inputStyle} />
        </div>
         <div>
          <label htmlFor="from_email" style={labelStyle}>From Email:</label>
          <input type="email" id="from_email" name="from_email" value={formData.from_email} onChange={handleChange} required style={inputStyle} />
        </div>
        <div>
          <label htmlFor="campaign_type" style={labelStyle}>Campaign Type:</label>
          <select name="campaign_type" value={formData.campaign_type} onChange={handleChange} style={inputStyle}>
            <option value="regular">Regular</option>
            <option value="optin">Opt-in</option>
          </select>
        </div>
        <div>
          <label htmlFor="content_type" style={labelStyle}>Content Type:</label>
          <select name="content_type" value={formData.content_type} onChange={handleChange} style={inputStyle}>
            <option value="html">HTML</option>
            <option value="richtext">Rich Text</option>
            <option value="plain">Plain Text</option>
            {/* <option value="markdown">Markdown</option> */}
            {/* <option value="visual">Visual Builder</option> */}
          </select>
        </div>
        <div>
          <label htmlFor="body" style={labelStyle}>Body Content:</label>
          <textarea id="body" name="body" value={formData.body} onChange={handleChange} rows={10} required style={{ ...inputStyle, width: '500px', height: '200px' }} />
        </div>

        {/* Placeholder for list selection - in a real app, this would be a multi-select or checkboxes */}
        <div>
            <h3 style={labelStyle}>Target Lists (Placeholder IDs: 1, 2, 3):</h3>
            {[1,2,3].map(listId => (
                 <label key={listId} style={{ marginRight: '10px'}}>
                    <input type="checkbox" checked={(formData.target_list_ids || []).includes(listId)} onChange={() => handleListSelection(listId)} />
                    List {listId}
                </label>
            ))}
        </div>

        {/* Placeholder for template selection */}
        {/* <div>
          <label htmlFor="template_id" style={labelStyle}>Template (Optional ID):</label>
          <input type="number" id="template_id" name="template_id" value={formData.template_id || ''} onChange={e => setFormData({...formData, template_id: e.target.value ? parseInt(e.target.value) : null})} style={inputStyle} />
        </div> */}


        {error && <p style={{ color: 'red' }}>{error}</p>}
        <button type="submit" disabled={isLoading} style={{ padding: '10px 20px', marginTop: '20px' }}>
          {isLoading ? 'Creating...' : 'Create Campaign'}
        </button>
      </form>
    </div>
  );
}
