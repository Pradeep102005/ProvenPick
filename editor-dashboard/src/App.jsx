import { useState, useEffect } from 'react';

const API_BASE = "/staging-api/reviews";

function App() {
  const [reviews, setReviews] = useState([]);
  const [selectedReview, setSelectedReview] = useState(null);
  const [activeTab, setActiveTab] = useState("draft"); // draft | specs | proscons | affiliate | sources
  const [filterStatus, setFilterStatus] = useState("all"); // all | pending | approved | rejected | published
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Modals
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [showQueueModal, setShowQueueModal] = useState(false);
  
  // Custom Queue Input
  const [customUrl, setCustomUrl] = useState("");
  const [queueLoading, setQueueLoading] = useState(false);
  const [queueMsg, setQueueMsg] = useState(null);
  
  // Approve Inputs
  const [categoryId, setCategoryId] = useState(1);
  const [categoryName, setCategoryName] = useState("Audio Gear");
  
  // Reject Input
  const [rejectComments, setRejectComments] = useState("");

  const fetchReviews = async () => {
    setLoading(true);
    try {
      let url = API_BASE;
      if (filterStatus !== "all") {
        url += `?status=${filterStatus}`;
      }
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to retrieve staging reviews.");
      const data = await res.json();
      setReviews(data);
      setError(null);
      
      if (selectedReview) {
        const updated = data.find(r => r.product_uuid === selectedReview.product_uuid);
        if (updated) setSelectedReview(updated);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReviews();
  }, [filterStatus]);

  const selectReview = (review) => {
    setSelectedReview(review);
    setActiveTab("draft");
    setCategoryId(review.l3_category_id || 1);
    setCategoryName(review.category_name || "Audio Gear");
  };

  const handleApprove = async () => {
    if (!selectedReview) return;
    try {
      const res = await fetch(`${API_BASE}/${selectedReview.product_uuid}/approve`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category_name: categoryName, l3_category_id: Number(categoryId) })
      });
      if (!res.ok) throw new Error("Approval action failed on staging server.");
      
      setShowApproveModal(false);
      await fetchReviews();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleReject = async () => {
    if (!selectedReview || !rejectComments.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/${selectedReview.product_uuid}/reject`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ editor_comments: rejectComments })
      });
      if (!res.ok) throw new Error("Rejection action failed on staging server.");
      
      setShowRejectModal(false);
      setRejectComments("");
      await fetchReviews();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleQueueCustomUrl = async (e) => {
    e.preventDefault();
    if (!customUrl.trim()) return;
    setQueueLoading(true);
    setQueueMsg(null);
    try {
      const res = await fetch(`${API_BASE}/enqueue-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: customUrl.trim() })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to queue YouTube URL.");
      
      setQueueMsg({ type: "success", text: data.message });
      setCustomUrl("");
      setTimeout(() => {
        setShowQueueModal(false);
        setQueueMsg(null);
        fetchReviews();
      }, 1500);
    } catch (err) {
      setQueueMsg({ type: "error", text: err.message });
    } finally {
      setQueueLoading(false);
    }
  };

  return (
    <div className="dashboard-layout">
      {/* Sidebar Navigation & Controls */}
      <aside className="sidebar">
        <div className="brand flex-between">
          <div className="flex-align gap-2">
            <span className="brand-logo">PP</span>
            <h1>ProvenPick Staging</h1>
          </div>
          <button 
            className="btn btn-secondary btn-sm"
            onClick={() => setShowQueueModal(true)}
            style={{ fontSize: '12px', padding: '6px 10px', background: '#3b82f6', color: '#fff' }}
          >
            ➕ Queue URL
          </button>
        </div>

        <div className="filter-group">
          {["all", "pending", "published", "rejected"].map((status) => (
            <button
              key={status}
              className={`filter-chip ${filterStatus === status ? 'active' : ''}`}
              onClick={() => setFilterStatus(status)}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>

        <div className="review-list">
          {loading && <div className="p-4 text-muted">Loading staging queue...</div>}
          {error && <div className="p-4 text-error">Error: {error}</div>}
          
          {!loading && reviews.length === 0 && (
            <div className="p-4 text-muted">No reviews in this queue.</div>
          )}

          {reviews.map((r) => (
            <div
              key={r.product_uuid}
              className={`review-card ${selectedReview?.product_uuid === r.product_uuid ? 'selected' : ''}`}
              onClick={() => selectReview(r)}
            >
              <div className="flex-between mb-1">
                <span className="brand-tag">{r.brand || "GENERIC"}</span>
                <span className={`status-badge status-${r.status}`}>{r.status.toUpperCase()}</span>
              </div>
              <h3 className="card-title">{r.review_title}</h3>
              <div className="card-meta flex-between">
                <span>{r.name}</span>
                <span>{new Date(r.submitted_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* Main Review Workspace */}
      <main className="workspace">
        {selectedReview ? (
          <>
            <header className="workspace-header">
              <div>
                <span className="text-secondary text-sm">{selectedReview.brand}</span>
                <h2>{selectedReview.name}</h2>
              </div>
              
              <div className="flex-align gap-2">
                <button className="btn btn-secondary">★ Pin to Homepage Flashcard</button>

                {selectedReview.status === "pending" && (
                  <>
                    <button 
                      className="btn btn-danger"
                      onClick={() => setShowRejectModal(true)}
                    >
                      ✕ Reject & Request AI Rewrite
                    </button>
                    
                    <button 
                      className="btn btn-success"
                      onClick={() => setShowApproveModal(true)}
                    >
                      ✓ Approve & Publish Now
                    </button>
                  </>
                )}

                {selectedReview.status === "published" && (
                  <span className="badge badge-success">🚀 PUBLISHED TO LIVE SITE</span>
                )}
              </div>
            </header>

            <nav className="tab-bar">
              <button 
                className={`tab-btn ${activeTab === 'draft' ? 'active' : ''}`}
                onClick={() => setActiveTab('draft')}
              >
                Draft Review
              </button>
              <button 
                className={`tab-btn ${activeTab === 'proscons' ? 'active' : ''}`}
                onClick={() => setActiveTab('proscons')}
              >
                Pros & Cons
              </button>
              <button 
                className={`tab-btn ${activeTab === 'specs' ? 'active' : ''}`}
                onClick={() => setActiveTab('specs')}
              >
                Specifications
              </button>
              <button 
                className={`tab-btn ${activeTab === 'affiliate' ? 'active' : ''}`}
                onClick={() => setActiveTab('affiliate')}
              >
                Affiliate Links
              </button>
              <button 
                className={`tab-btn ${activeTab === 'sources' ? 'active' : ''}`}
                onClick={() => setActiveTab('sources')}
              >
                Sources
              </button>
            </nav>

            <div className="content-area">
              {activeTab === 'draft' && (
                <div className="draft-view">
                  <div className="verdict-card">
                    <span className="verdict-title">AI SUMMARY VERDICT</span>
                    <p>{selectedReview.summary}</p>
                  </div>
                  <h3>{selectedReview.review_title}</h3>
                  <p><strong>Verdict:</strong> {selectedReview.verdict}</p>
                  
                  {selectedReview.review_sections.map((sec, idx) => (
                    <div key={idx} className="mb-4" style={{ marginTop: '20px' }}>
                      <h4 style={{ fontSize: '18px', color: '#60a5fa' }}>{sec.title}</h4>
                      <div dangerouslySetInnerHTML={{ __html: sec.content_html }} style={{ lineHeight: '1.7', color: '#d1d5db' }} />
                    </div>
                  ))}
                </div>
              )}

              {activeTab === 'proscons' && (
                <div className="pros-cons-grid">
                  <div className="pros-box">
                    <h3>Pros</h3>
                    <ul>
                      {selectedReview.pros.map((p, idx) => (
                        <li key={idx}>+ {typeof p === 'string' ? p : p.text}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="cons-box">
                    <h3>Cons</h3>
                    <ul>
                      {selectedReview.cons.map((c, idx) => (
                        <li key={idx}>- {typeof c === 'string' ? c : c.text}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {activeTab === 'specs' && (
                <table className="specs-table">
                  <tbody>
                    {Object.entries(selectedReview.specs || {}).map(([k, v]) => (
                      <tr key={k}>
                        <td className="spec-key">{k}</td>
                        <td className="spec-val">{String(v)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {activeTab === 'affiliate' && (
                <div className="affiliate-list">
                  {selectedReview.affiliate_links.map((link, idx) => (
                    <div key={idx} className="affiliate-card flex-between">
                      <div>
                        <strong>{link.platform?.toUpperCase()}</strong>
                        <div className="text-secondary text-sm">{link.tracked_url}</div>
                      </div>
                      <a href={link.tracked_url} target="_blank" rel="noreferrer" className="btn btn-secondary">Test Link</a>
                    </div>
                  ))}
                </div>
              )}

              {activeTab === 'sources' && (
                <div className="sources-list">
                  {selectedReview.sources.map((src, idx) => (
                    <div key={idx} className="source-card flex-between">
                      <div>
                        <strong>{src.video_title}</strong>
                        <div className="text-secondary text-sm">{src.channel_name}</div>
                      </div>
                      <a href={src.video_url} target="_blank" rel="noreferrer" className="btn btn-secondary">🔗</a>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">✍️</div>
            <h2>Select a review from staging list</h2>
            <p>You can verify specifications, read draft guides, and publish directly to live site</p>
          </div>
        )}
      </main>

      {/* Queue Custom YouTube URL Modal */}
      {showQueueModal && (
        <div className="modal-backdrop">
          <div className="modal-content">
            <h3>➕ Queue Custom YouTube Video</h3>
            <p className="text-secondary text-sm mb-3">
              Paste a YouTube review link to immediately queue it into the AI pipeline.
            </p>
            <form onSubmit={handleQueueCustomUrl}>
              <div className="form-group mb-3">
                <label>YouTube Video URL:</label>
                <input
                  type="url"
                  className="form-input"
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={customUrl}
                  onChange={(e) => setCustomUrl(e.target.value)}
                  required
                />
              </div>

              {queueMsg && (
                <div className={`p-2 mb-3 ${queueMsg.type === 'error' ? 'text-error' : 'text-success'}`} style={{ fontSize: '13px' }}>
                  {queueMsg.text}
                </div>
              )}

              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowQueueModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-success" disabled={queueLoading}>
                  {queueLoading ? "Queuing..." : "Queue to AI Pipeline"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Approve Modal */}
      {showApproveModal && (
        <div className="modal-backdrop">
          <div className="modal-content">
            <h3>Approve & Publish Review</h3>
            <p className="text-secondary text-sm mb-3">
              Select the final taxonomy category before pushing live to website.
            </p>
            <div className="form-group mb-3">
              <label>Category Name:</label>
              <input
                type="text"
                className="form-input"
                value={categoryName}
                onChange={(e) => setCategoryName(e.target.value)}
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowApproveModal(false)}>Cancel</button>
              <button className="btn btn-success" onClick={handleApprove}>Confirm & Publish Live</button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="modal-backdrop">
          <div className="modal-content">
            <h3>Reject Review & Request Rewrite</h3>
            <p className="text-secondary text-sm mb-3">
              Provide feedback for the AI Scribe Agent to rewrite the draft.
            </p>
            <textarea
              className="form-input mb-3"
              rows={4}
              placeholder="e.g. Include detailed display brightness comparisons..."
              value={rejectComments}
              onChange={(e) => setRejectComments(e.target.value)}
            />
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowRejectModal(false)}>Cancel</button>
              <button className="btn btn-danger" onClick={handleReject}>Reject & Rewrite</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
