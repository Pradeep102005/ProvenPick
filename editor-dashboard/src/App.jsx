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
  
  // Approve Inputs
  const [categoryId, setCategoryId] = useState(1);
  const [categoryName, setCategoryName] = useState("Audio Gear");
  
  // Reject Input
  const [rejectComments, setRejectComments] = useState("");

  // Fetch reviews
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
      
      // Keep selected review updated if it is currently open
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
    // Prepopulate approval form from selected review if present
    setCategoryId(review.l3_category_id || 1);
    setCategoryName(review.category_name || "Audio Gear");
  };

  const handleApprove = async () => {
    if (!selectedReview) return;
    try {
      const res = await fetch(`${API_BASE}/${selectedReview.product_uuid}/approve`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      if (!res.ok) throw new Error("Approval action failed on staging server.");
      
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
        body: JSON.stringify({
          editor_comments: rejectComments
        })
      });
      if (!res.ok) throw new Error("Rejection action failed on staging server.");
      
      setShowRejectModal(false);
      setRejectComments("");
      await fetchReviews();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo-icon">PP</div>
          <span className="logo-text">ProvenPick Staging</span>
        </div>
        
        <div className="sidebar-filters">
          <button 
            className={`filter-btn ${filterStatus === "all" ? "active" : ""}`}
            onClick={() => setFilterStatus("all")}
          >
            All
          </button>
          <button 
            className={`filter-btn ${filterStatus === "pending" ? "active" : ""}`}
            onClick={() => setFilterStatus("pending")}
          >
            Pending
          </button>
          <button 
            className={`filter-btn ${filterStatus === "published" ? "active" : ""}`}
            onClick={() => setFilterStatus("published")}
          >
            Published
          </button>
          <button 
            className={`filter-btn ${filterStatus === "rejected" ? "active" : ""}`}
            onClick={() => setFilterStatus("rejected")}
          >
            Rejected
          </button>
        </div>

        <div className="review-list">
          {loading && <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)' }}>Loading review drafts...</div>}
          {error && <div style={{ color: 'var(--danger)', padding: '10px 0' }}>Error: {error}</div>}
          {!loading && reviews.length === 0 && (
            <div style={{ textAlign: 'center', padding: '40px 10px', color: 'var(--text-dim)' }}>
              No reviews in this queue.
            </div>
          )}
          
          {reviews.map(review => (
            <div 
              key={review.id}
              className={`review-card ${selectedReview?.product_uuid === review.product_uuid ? "selected" : ""}`}
              onClick={() => selectReview(review)}
            >
              <div className="review-card-header">
                <span className="review-card-brand">{review.brand || "Consensus"}</span>
                <span className={`status-badge ${review.status}`}>{review.status}</span>
              </div>
              <h3 className="review-card-title">{review.review_title}</h3>
              <div className="review-card-meta">
                <span>{review.name}</span>
                <span>{new Date(review.submitted_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* Main Preview Panel */}
      <main className="preview-panel">
        {selectedReview ? (
          <>
            {/* Header */}
            <div className="detail-header">
              <div className="detail-title-area">
                <span className="detail-title-brand">{selectedReview.brand || "Consensus Guide"}</span>
                <h1 className="detail-title">{selectedReview.name}</h1>
              </div>
              
              <div className="detail-actions">
                {selectedReview.status === "pending" && (
                  <>
                    <button 
                      className="action-btn approve"
                      onClick={handleApprove}
                    >
                      ✓ Approve & Publish Now
                    </button>
                    <button 
                      className="action-btn reject"
                      onClick={() => setShowRejectModal(true)}
                    >
                      Reject Draft
                    </button>
                  </>
                )}
                <button 
                  className="action-btn"
                  style={{ background: selectedReview.is_featured ? '#eab308' : '#3a3a46', color: selectedReview.is_featured ? '#000' : '#fff', marginLeft: '10px', padding: '10px 16px', borderRadius: '8px', cursor: 'pointer', fontWeight: '700' }}
                  onClick={async () => {
                    try {
                      const res = await fetch(`${API_BASE}/${selectedReview.product_uuid}/feature`, { method: "PATCH" });
                      if (!res.ok) throw new Error("Failed to update feature status");
                      await fetchReviews();
                    } catch (err) {
                      alert(err.message);
                    }
                  }}
                >
                  {selectedReview.is_featured ? '⭐ Featured on Homepage Flashcard' : '☆ Pin to Homepage Flashcard'}
                </button>
                {selectedReview.status === "published" && (
                  <span className="status-badge published" style={{ padding: '10px 16px', borderRadius: '8px', marginLeft: '10px' }}>
                    🚀 Published to Live Site
                  </span>
                )}
                {selectedReview.status === "rejected" && (
                  <span className="status-badge rejected" style={{ padding: '10px 16px', borderRadius: '8px' }}>
                    🔄 Loop Active: Awaiting AI Rewrite
                  </span>
                )}
              </div>
            </div>

            {/* Tabs */}
            <div className="detail-tabs">
              <button 
                className={`tab-btn ${activeTab === "draft" ? "active" : ""}`}
                onClick={() => setActiveTab("draft")}
              >
                Draft Review
              </button>
              <button 
                className={`tab-btn ${activeTab === "proscons" ? "active" : ""}`}
                onClick={() => setActiveTab("proscons")}
              >
                Pros & Cons
              </button>
              <button 
                className={`tab-btn ${activeTab === "specs" ? "active" : ""}`}
                onClick={() => setActiveTab("specs")}
              >
                Specifications
              </button>
              <button 
                className={`tab-btn ${activeTab === "affiliate" ? "active" : ""}`}
                onClick={() => setActiveTab("affiliate")}
              >
                Affiliate Links
              </button>
              <button 
                className={`tab-btn ${activeTab === "sources" ? "active" : ""}`}
                onClick={() => setActiveTab("sources")}
              >
                Sources
              </button>
            </div>

            {/* Tab Contents */}
            <div className="detail-content">
              {activeTab === "draft" && (
                <div style={{ maxWidth: '800px' }}>
                  <div style={{ marginBottom: '24px', padding: '16px 20px', background: 'rgba(255,255,255,0.02)', borderRadius: '10px', borderLeft: '3px solid var(--accent-primary)' }}>
                    <h4 style={{ fontSize: '12px', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>AI Summary Verdict</h4>
                    <p style={{ fontSize: '15px', lineHeight: '1.6' }}>{selectedReview.summary}</p>
                  </div>
                  
                  {selectedReview.editor_comments && (
                    <div style={{ marginBottom: '24px', padding: '16px 20px', background: 'rgba(248,113,113,0.05)', borderRadius: '10px', borderLeft: '3px solid var(--danger)' }}>
                      <h4 style={{ fontSize: '12px', textTransform: 'uppercase', color: 'var(--danger)', marginBottom: '4px' }}>Latest Editor Critique Comments</h4>
                      <p style={{ fontSize: '14px', fontStyle: 'italic' }}>"{selectedReview.editor_comments}"</p>
                    </div>
                  )}

                  <div className="html-preview">
                    {selectedReview.review_sections?.map(section => (
                      <div key={section.page_index} style={{ marginBottom: '32px' }}>
                        <h2>{section.title}</h2>
                        <div dangerouslySetInnerHTML={{ __html: section.content_html }} />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {activeTab === "proscons" && (
                <div className="pros-cons-container">
                  <div className="pro-con-box">
                    <h2 className="pro-con-header pros">
                      <span>🟢</span> Pros
                    </h2>
                    <div className="pro-con-list">
                      {selectedReview.pros?.map((pro, index) => (
                        <div key={index} className="pro-con-item pro">
                          <span className="pro-con-text">{pro.text}</span>
                          <span className="pro-con-weight">Weight: {pro.weight || 5}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="pro-con-box">
                    <h2 className="pro-con-header cons">
                      <span>🔴</span> Cons
                    </h2>
                    <div className="pro-con-list">
                      {selectedReview.cons?.map((con, index) => (
                        <div key={index} className="pro-con-item con">
                          <span className="pro-con-text">{con.text}</span>
                          <span className="pro-con-weight">Weight: {con.weight || 3}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "specs" && (
                <div className="specs-grid">
                  {Object.entries(selectedReview.specs || {}).map(([key, val]) => (
                    <div key={key} className="spec-item">
                      <div className="spec-key">{key}</div>
                      <div className="spec-val">{String(val)}</div>
                    </div>
                  ))}
                </div>
              )}

              {activeTab === "affiliate" && (
                <div className="specs-grid">
                  {Object.entries(selectedReview.affiliate_links || {}).map(([platform, url]) => (
                    <div key={platform} className="spec-item">
                      <div className="spec-key" style={{ color: 'var(--success)' }}>{platform}</div>
                      <a href={url} target="_blank" rel="noopener noreferrer" className="spec-val" style={{ color: 'var(--accent-primary)', textDecoration: 'underline', wordBreak: 'break-all' }}>
                        {url}
                      </a>
                    </div>
                  ))}
                </div>
              )}

              {activeTab === "sources" && (
                <div className="sources-list">
                  {selectedReview.sources?.map((src, index) => (
                    <a 
                      key={index} 
                      href={src.video_url} 
                      target="_blank" 
                      rel="noopener noreferrer" 
                      className="source-item"
                    >
                      <div className="source-info">
                        <h4 className="source-title">{src.video_title}</h4>
                        <span className="source-channel">{src.channel_name}</span>
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

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2 className="modal-title">Reject Review Draft</h2>
            <p className="modal-desc">
              Specify what the Scribe Agent needs to adjust (e.g. wrong facts, bad formatting). This triggers the LangGraph agent to rewrite the review.
            </p>
            
            <div className="modal-form-group">
              <label>critique comments</label>
              <textarea 
                className="modal-input modal-textarea"
                placeholder="Detail the corrections here..."
                value={rejectComments}
                onChange={(e) => setRejectComments(e.target.value)}
              />
            </div>

            <div className="modal-actions">
              <button className="modal-btn cancel" onClick={() => setShowRejectModal(false)}>
                Cancel
              </button>
              <button className="modal-btn" style={{ background: 'var(--danger)', color: '#fff' }} onClick={handleReject}>
                Submit to Rewrite
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
