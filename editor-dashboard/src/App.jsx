import { useState, useEffect } from 'react';
import './index.css';

const API_BASE = "/staging-api/reviews";

function App() {
  const [reviews, setReviews] = useState([]);
  const [selectedReview, setSelectedReview] = useState(null);
  const [activeTab, setActiveTab] = useState("draft"); // draft | proscons | specs | affiliate | sources
  const [filterStatus, setFilterStatus] = useState("all"); // all | pending | approved | rejected | published
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Modals
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [showQueueModal, setShowQueueModal] = useState(false);
  
  // Toast Popup Notification
  const [toast, setToast] = useState(null); // { message: string, url: string }
  
  // Custom Queue Input
  const [customUrl, setCustomUrl] = useState("");
  const [queueLoading, setQueueLoading] = useState(false);
  const [queueMsg, setQueueMsg] = useState(null);
  
  // Approve Inputs
  const [categoryName, setCategoryName] = useState("Smartphones");
  const [l3CategoryId, setL3CategoryId] = useState(1);
  
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
      } else if (data.length > 0) {
        setSelectedReview(data[0]);
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
    setCategoryName(review.category_name || "Smartphones");
    setL3CategoryId(review.l3_category_id || 1);
  };

  const triggerToast = (message, url = null) => {
    setToast({ message, url });
    setTimeout(() => {
      setToast(null);
    }, 6000);
  };

  const handleApprove = async () => {
    if (!selectedReview) return;
    try {
      const res = await fetch(`${API_BASE}/${selectedReview.product_uuid}/approve`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category_name: categoryName, l3_category_id: Number(l3CategoryId) })
      });
      if (!res.ok) throw new Error("Approval action failed on staging server.");
      
      setShowApproveModal(false);
      const approvedTitle = selectedReview.name || selectedReview.review_title;
      triggerToast(
        `🚀 "${approvedTitle}" review was successfully approved and published live to provenpick.xyz!`,
        "https://provenpick.xyz"
      );
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
      triggerToast(`🔄 Review returned to Scribe AI pipeline for rewrite with comments.`);
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
      triggerToast(`📥 YouTube video queued into AI review writer pipeline!`);
      setTimeout(() => {
        setShowQueueModal(false);
        setQueueMsg(null);
        fetchReviews();
      }, 1200);
    } catch (err) {
      setQueueMsg({ type: "error", text: err.message });
    } finally {
      setQueueLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Sliding Toast Popup Notification */}
      {toast && (
        <div 
          style={{
            position: 'fixed',
            top: '24px',
            right: '24px',
            zIndex: 9999,
            background: '#10b981',
            color: '#042f2e',
            padding: '16px 24px',
            borderRadius: '12px',
            boxShadow: '0 10px 30px rgba(16, 185, 129, 0.4)',
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            fontWeight: '600',
            animation: 'slideIn 0.3s ease-out',
            maxWidth: '500px'
          }}
        >
          <span style={{ fontSize: '20px' }}>⚡</span>
          <div>
            <div style={{ fontSize: '14px', lineHeight: '1.4' }}>{toast.message}</div>
            {toast.url && (
              <a 
                href={toast.url} 
                target="_blank" 
                rel="noreferrer"
                style={{ color: '#042f2e', textDecoration: 'underline', fontWeight: 'bold', fontSize: '13px', marginTop: '4px', display: 'inline-block' }}
              >
                View Live on Website →
              </a>
            )}
          </div>
          <button 
            onClick={() => setToast(null)}
            style={{ background: 'transparent', border: 'none', color: '#042f2e', cursor: 'pointer', fontSize: '16px', fontWeight: 'bold' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="sidebar-header" style={{ justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div className="logo-icon">PP</div>
            <div className="logo-text">ProvenPick Staging</div>
          </div>
          <button 
            className="filter-btn"
            onClick={() => setShowQueueModal(true)}
            style={{ background: '#6366f1', color: '#fff', fontWeight: 'bold', padding: '6px 12px' }}
          >
            ➕ Queue URL
          </button>
        </div>

        <div className="sidebar-filters">
          {["all", "pending", "published", "rejected"].map((status) => (
            <button
              key={status}
              className={`filter-btn ${filterStatus === status ? 'active' : ''}`}
              onClick={() => setFilterStatus(status)}
            >
              {status.toUpperCase()}
            </button>
          ))}
        </div>

        <div className="review-list">
          {loading && <div style={{ padding: '24px', color: 'var(--text-muted)' }}>Loading review queue...</div>}
          {error && <div style={{ padding: '24px', color: 'var(--danger)' }}>Error: {error}</div>}
          
          {!loading && reviews.length === 0 && (
            <div style={{ padding: '24px', color: 'var(--text-muted)', textAlign: 'center' }}>
              No reviews found in queue.
            </div>
          )}

          {reviews.map((r) => (
            <div
              key={r.product_uuid}
              className={`review-card ${selectedReview?.product_uuid === r.product_uuid ? 'selected' : ''}`}
              onClick={() => selectReview(r)}
            >
              <div className="review-card-header">
                <span className="review-card-brand">{r.brand || "GENERIC"}</span>
                <span className={`status-badge ${r.status}`}>{r.status.toUpperCase()}</span>
              </div>
              <div className="review-card-title">{r.review_title}</div>
              <div className="review-card-meta">
                <span>{r.name}</span>
                <span>{new Date(r.submitted_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* Main Preview Panel */}
      <main className="preview-panel">
        {selectedReview ? (
          <>
            <div className="detail-header">
              <div className="detail-title-area">
                <span className="detail-title-brand">{selectedReview.brand}</span>
                <h2 className="detail-title">{selectedReview.name}</h2>
              </div>
              
              <div className="detail-actions">
                <button className="action-btn" style={{ background: 'rgba(255,255,255,0.08)', color: '#fff' }}>
                  ★ Pin Flashcard
                </button>

                {selectedReview.status === "pending" && (
                  <>
                    <button 
                      className="action-btn reject"
                      onClick={() => setShowRejectModal(true)}
                    >
                      ✕ Reject & Request Rewrite
                    </button>
                    
                    <button 
                      className="action-btn approve"
                      onClick={() => setShowApproveModal(true)}
                    >
                      ✓ Approve & Publish Now
                    </button>
                  </>
                )}

                {selectedReview.status === "published" && (
                  <span className="status-badge published" style={{ fontSize: '13px', padding: '8px 16px' }}>
                    🚀 PUBLISHED LIVE
                  </span>
                )}
              </div>
            </div>

            <div className="detail-tabs">
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
            </div>

            <div className="detail-content">
              {activeTab === 'draft' && (
                <div>
                  <div style={{ background: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.3)', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
                    <div style={{ color: '#818cf8', fontWeight: 'bold', fontSize: '12px', letterSpacing: '1px', marginBottom: '6px' }}>AI SUMMARY VERDICT</div>
                    <p style={{ color: '#e0e7ff', lineHeight: '1.6' }}>{selectedReview.summary}</p>
                  </div>

                  <h3 style={{ fontSize: '22px', marginBottom: '12px' }}>{selectedReview.review_title}</h3>
                  <p style={{ marginBottom: '24px', color: '#9ca3af' }}><strong>Verdict:</strong> {selectedReview.verdict}</p>
                  
                  <div className="html-preview">
                    {selectedReview.review_sections.map((sec, idx) => (
                      <div key={idx} style={{ marginBottom: '28px' }}>
                        <h3 style={{ color: '#818cf8', marginBottom: '12px' }}>{sec.title}</h3>
                        <div dangerouslySetInnerHTML={{ __html: sec.content_html }} />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {activeTab === 'proscons' && (
                <div className="pros-cons-container">
                  <div className="pro-con-box">
                    <div className="pro-con-header pros">PROS</div>
                    <div className="pro-con-list">
                      {selectedReview.pros.map((p, idx) => (
                        <div key={idx} className="pro-con-item pro">
                          <span className="pro-con-text">+ {typeof p === 'string' ? p : p.text}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="pro-con-box">
                    <div className="pro-con-header cons">CONS</div>
                    <div className="pro-con-list">
                      {selectedReview.cons.map((c, idx) => (
                        <div key={idx} className="pro-con-item con">
                          <span className="pro-con-text">- {typeof c === 'string' ? c : c.text}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'specs' && (
                <div className="specs-grid">
                  {Object.entries(selectedReview.specs || {}).map(([k, v]) => (
                    <div key={k} className="spec-item">
                      <div className="spec-key">{k}</div>
                      <div className="spec-val">{String(v)}</div>
                    </div>
                  ))}
                </div>
              )}

              {activeTab === 'affiliate' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {selectedReview.affiliate_links.map((link, idx) => (
                    <div key={idx} className="source-item">
                      <div>
                        <div className="source-title">{link.platform?.toUpperCase()}</div>
                        <div className="source-channel">{link.tracked_url}</div>
                      </div>
                      <a href={link.tracked_url} target="_blank" rel="noreferrer" className="modal-btn cancel">Test Link</a>
                    </div>
                  ))}
                </div>
              )}

              {activeTab === 'sources' && (
                <div className="sources-list">
                  {selectedReview.sources.map((src, idx) => (
                    <a key={idx} href={src.video_url} target="_blank" rel="noreferrer" className="source-item">
                      <div className="source-info">
                        <div className="source-title">{src.video_title}</div>
                        <div className="source-channel">{src.channel_name}</div>
                      </div>
                      <span className="source-link-icon">🔗</span>
                    </a>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="empty-state">
            <div className="empty-state-icon">✍️</div>
            <h2>Select a review from staging list</h2>
            <p>You can verify specifications, read draft guides, and publish directly to live site</p>
          </div>
        )}
      </main>

      {/* Queue Custom YouTube URL Modal */}
      {showQueueModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-title">➕ Queue Custom YouTube Video</div>
            <div className="modal-desc">
              Paste a YouTube review link to immediately queue it into the AI pipeline.
            </div>
            <form onSubmit={handleQueueCustomUrl}>
              <div className="modal-form-group">
                <label>YouTube Video URL:</label>
                <input
                  type="url"
                  className="modal-input"
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={customUrl}
                  onChange={(e) => setCustomUrl(e.target.value)}
                  required
                />
              </div>

              {queueMsg && (
                <div style={{ color: queueMsg.type === 'error' ? 'var(--danger)' : 'var(--success)', marginBottom: '16px', fontSize: '13px' }}>
                  {queueMsg.text}
                </div>
              )}

              <div className="modal-actions">
                <button type="button" className="modal-btn cancel" onClick={() => setShowQueueModal(false)}>Cancel</button>
                <button type="submit" className="action-btn approve" disabled={queueLoading}>
                  {queueLoading ? "Queuing..." : "Queue to AI Pipeline"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Approve Modal */}
      {showApproveModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-title">Approve & Publish Review</div>
            <div className="modal-desc">
              Select the final taxonomy category before pushing live to website.
            </div>
            <div className="modal-form-group">
              <label>Category Name:</label>
              <input
                type="text"
                className="modal-input"
                value={categoryName}
                onChange={(e) => setCategoryName(e.target.value)}
              />
            </div>
            <div className="modal-actions">
              <button className="modal-btn cancel" onClick={() => setShowApproveModal(false)}>Cancel</button>
              <button className="action-btn approve" onClick={handleApprove}>Confirm & Publish Live</button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-title">Reject Review & Request Rewrite</div>
            <div className="modal-desc">
              Provide feedback for the AI Scribe Agent to rewrite the draft.
            </div>
            <textarea
              className="modal-input modal-textarea"
              placeholder="e.g. Include detailed display brightness comparisons..."
              value={rejectComments}
              onChange={(e) => setRejectComments(e.target.value)}
            />
            <div className="modal-actions">
              <button className="modal-btn cancel" onClick={() => setShowRejectModal(false)}>Cancel</button>
              <button className="action-btn reject" onClick={handleReject}>Reject & Rewrite</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
