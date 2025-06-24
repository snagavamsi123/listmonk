// app/(dashboard)/campaigns/page.jsx
"use client"; // For client-side data fetching and interactivity.

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { getCampaigns, deleteCampaign } from '@/lib/api'; // Use .js extension

// No more TypeScript interfaces, rely on JSDoc in api.js or inline understanding
// Or define prop types if using 'prop-types' library, though less common with modern React/Next.js

export default function CampaignsPage() {
  const [campaignsResponse, setCampaignsResponse] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const perPage = 10;

  useEffect(() => {
    async function loadCampaigns() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getCampaigns(page, perPage);
        setCampaignsResponse(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An unknown error occurred');
      } finally {
        setIsLoading(false);
      }
    }
    loadCampaigns();
  }, [page]);

  const handleDelete = async (uuid) => { // Changed id to uuid
    if (window.confirm('Are you sure you want to delete this campaign?')) {
      try {
        await deleteCampaign(uuid);
        setCampaignsResponse(prev => prev ? ({
          ...prev,
          results: prev.results.filter(c => c.uuid !== uuid), // filter by uuid
          count: prev.count -1,
        }) : null);
      } catch (err) {
        alert('Failed to delete campaign: ' + (err instanceof Error ? err.message : 'Unknown error'));
      }
    }
  };

  if (isLoading) return <p className="p-4 text-center text-gray-500">Loading campaigns...</p>;
  if (error) return <p className="p-4 text-center text-red-500">Error loading campaigns: {error}</p>;
  if (!campaignsResponse || campaignsResponse.results.length === 0) {
    return (
        <div className="p-8 text-center">
            <p className="text-gray-600 mb-4">No campaigns found.</p>
            <Link href="/campaigns/new" className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors">
                Create Your First Campaign
            </Link>
        </div>
    );
  }

  return (
    <div className="container mx-auto p-4 md:p-6 lg:p-8">
      {/* UI/UX Note: Consistent header, clear actions, good visual hierarchy are key */}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-semibold text-gray-800">Campaigns</h1>
        <Link href="/campaigns/new" className="px-4 py-2 bg-green-500 text-white rounded-md hover:bg-green-600 transition-colors shadow-sm">
          + Create New Campaign
        </Link>
      </div>

      {/* UI/UX Note: Responsive table, clear data presentation, intuitive actions */}
      <div className="bg-white shadow-md rounded-lg overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subject</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created At</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {campaignsResponse.results.map((campaign) => (
              <tr key={campaign.uuid} className="hover:bg-gray-50 transition-colors"> {/* Use uuid for key */}
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  {/* UI/UX Note: Link should be clearly identifiable */}
                  <Link href={`/campaigns/${campaign.uuid}`} className="text-blue-600 hover:text-blue-800 hover:underline">
                    {campaign.name}
                  </Link>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{campaign.subject}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {/* UI/UX Note: Status badges can improve readability */}
                  <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full
                                   ${campaign.status === 'draft' ? 'bg-yellow-100 text-yellow-800' :
                                     campaign.status === 'sent' || campaign.status === 'finished' ? 'bg-green-100 text-green-800' :
                                     campaign.status === 'running' || campaign.status === 'scheduled' ? 'bg-blue-100 text-blue-800' :
                                     'bg-gray-100 text-gray-800'}`}>
                    {campaign.status}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {new Date(campaign.created_at).toLocaleDateString()}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  {/* UI/UX Note: Action buttons should have clear affordance and spacing */}
                  <Link href={`/campaigns/${campaign.uuid}/edit`} className="text-indigo-600 hover:text-indigo-900 mr-3">
                    Edit
                  </Link>
                  <button
                    onClick={() => handleDelete(campaign.uuid)} // Use uuid
                    className="text-red-600 hover:text-red-900 focus:outline-none"
                    aria-label={`Delete campaign ${campaign.name}`}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* UI/UX Note: Pagination should be clear and easy to use */}
      <div className="mt-6 flex justify-center items-center space-x-2">
        {campaignsResponse.previous && (
          <button
            onClick={() => setPage(page - 1)}
            disabled={isLoading}
            className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            Previous
          </button>
        )}
        <span className="text-sm text-gray-700">
          Page {page} of {Math.ceil(campaignsResponse.count / perPage)} (Total: {campaignsResponse.count})
        </span>
        {campaignsResponse.next && (
          <button
            onClick={() => setPage(page + 1)}
            disabled={isLoading}
            className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            Next
          </button>
        )}
      </div>
    </div>
  );
}
