// app/(dashboard)/campaigns/page.tsx
"use client"; // For client-side data fetching and interactivity. Remove if using RSC for fetching.

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { getCampaigns, deleteCampaign } from '@/lib/api'; // Assuming api.ts is in lib

// Define a simple type for Campaign for the frontend, can be more detailed
interface CampaignFE {
  id: number;
  name: string;
  subject: string;
  status: string;
  created_at: string;
  // Add more fields as needed for display
}

interface PaginatedCampaignsResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: CampaignFE[];
}

export default function CampaignsPage() {
  const [campaignsResponse, setCampaignsResponse] = useState<PaginatedCampaignsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const perPage = 10; // Or make this configurable

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
  }, [page]); // Reload when page changes

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this campaign?')) {
      try {
        await deleteCampaign(id);
        // Refresh list or remove item from state
        setCampaignsResponse(prev => prev ? ({
          ...prev,
          results: prev.results.filter(c => c.id !== id),
          count: prev.count -1,
        }) : null);
      } catch (err) {
        alert('Failed to delete campaign: ' + (err instanceof Error ? err.message : 'Unknown error'));
      }
    }
  };

  if (isLoading) return <p>Loading campaigns...</p>;
  if (error) return <p>Error loading campaigns: {error}</p>;
  if (!campaignsResponse || campaignsResponse.results.length === 0) return <p>No campaigns found.</p>;

  return (
    <div style={{ padding: '20px' }}>
      <h1>Campaigns</h1>
      <Link href="/campaigns/new" style={{ marginBottom: '20px', display: 'inline-block' }}>
        Create New Campaign
      </Link>

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Name</th>
            <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Subject</th>
            <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Status</th>
            <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Created At</th>
            <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {campaignsResponse.results.map((campaign) => (
            <tr key={campaign.id}>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                <Link href={`/campaigns/${campaign.id}`}>{campaign.name}</Link>
              </td>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{campaign.subject}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{campaign.status}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                {new Date(campaign.created_at).toLocaleDateString()}
              </td>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                <Link href={`/campaigns/${campaign.id}/edit`}>Edit</Link> {/* Assuming an edit page route */}
                {' | '}
                <button onClick={() => handleDelete(campaign.id)} style={{ color: 'red', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Pagination Controls */}
      <div style={{ marginTop: '20px' }}>
        {campaignsResponse.previous && (
          <button onClick={() => setPage(page - 1)} disabled={isLoading}>
            Previous
          </button>
        )}
        <span style={{ margin: '0 10px' }}>
          Page {page} of {Math.ceil(campaignsResponse.count / perPage)}
        </span>
        {campaignsResponse.next && (
          <button onClick={() => setPage(page + 1)} disabled={isLoading}>
            Next
          </button>
        )}
      </div>
    </div>
  );
}
