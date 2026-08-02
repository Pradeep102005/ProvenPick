import { useState, useEffect } from 'react';

const API_BASE = "http://localhost:8002/api/articles";

function App() {
  const [articles, setArticles] = useState([]);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [articleDetail, setArticleDetail] = useState(null);
  const [activeTab, setActiveTab] = useState("guide"); // guide | proscons | specs
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch all articles
  const fetchArticles = async () => {
    setLoading(true);
    try {
      const res = await fetch(API_BASE);
      if (!res.ok) throw new Error("Failed to load buying guides.");
      const data = await res.json();
      setArticles(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchArticles();
  }, []);

  // Fetch article detail
  const loadArticleDetail = async (slug) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/${slug}`);
      if (!res.ok) throw new Error("Failed to load review details.");
      const data = await res.json();
      setArticleDetail(data);
      setActiveTab("guide");
      
      // Increment view count in production API
      fetch(`${API_BASE}/${slug}/view`, { method: "POST" }).catch(() => {});
    } catch (err) {
      alert(err.message);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleSelectArticle = (slug) => {
    setSelectedArticle(slug);
    loadArticleDetail(slug);
  };

  const handleBack = () => {
    setSelectedArticle(null);
    setArticleDetail(null);
    fetchArticles(); // refresh list to show updated view count
  };

  const handleAffiliateClick = async (linkId, url) => {
    // Record click count in production API
    try {
      await fetch(`${API_BASE}/affiliate/click/${linkId}`, { method: "POST" });
    } catch (err) {
      console.error("Failed to register affiliate click event", err);
    }
    // Open URL
    window.open(url, "_blank", "noopener,noreferrer");
  };

  return (
    <div>
      {/* Header */}
      <header className="site-header">
        <div className="container header-flex">
          <div className="brand" style={{ cursor: 'pointer' }} onClick={handleBack}>
            <div className="brand-logo">PP</div>
            <span className="brand-name">ProvenPick</span>
          </div>
          <nav className="header-nav">
            <span className="nav-link active" style={{ cursor: 'pointer' }} onClick={handleBack}>Buying Guides</span>
            <a href="https://github.com/Pradeep102005/ProvenPick" target="_blank" rel="noreferrer" className="nav-link">GitHub</a>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="container">
        {!selectedArticle ? (
          <>
            {/* Hero */}
            <section className="hero">
              <h1>Consensus-Driven Tech Reviews</h1>
              <p>
                Expert-curated, consensus-driven tech reviews and comparisons. Detailed analysis, verified facts, and direct buying recommendations. 100% independent and ad-free.
              </p>
            </section>

            {/* Catalog Grid */}
            {loading ? (
              <div style={{ textAlign: 'center', padding: '80px', color: 'var(--text-muted)' }}>Loading trusted buying guides...</div>
            ) : error ? (
              <div style={{ color: 'var(--danger)', textAlign: 'center', padding: '40px' }}>Error: {error}</div>
            ) : articles.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '80px', color: 'var(--text-dim)' }}>
                No guides published yet. Publish a review from Staging API to get started!
              </div>
            ) : (
              <section className="catalog-grid">
                {articles.map(art => (
                  <div key={art.id} className="article-card">
                    <span className="card-category">{art.category_name}</span>
                    <h2 className="card-title">{art.title}</h2>
                    <p className="card-intro">{art.introduction}</p>
                    <div className="card-footer">
                      <span>👀 {art.view_count || 0} views</span>
                      <button 
                        className="buy-button" 
                        style={{ padding: '8px 16px', fontSize: '13px', width: 'auto', margin: 0 }}
                        onClick={() => handleSelectArticle(art.slug)}
                      >
                        Read Guide
                      </button>
                    </div>
                  </div>
                ))}
              </section>
            )}
          </>
        ) : (
          /* Article Detail View */
          <>
            {detailLoading || !articleDetail ? (
              <div style={{ textAlign: 'center', padding: '80px', color: 'var(--text-muted)' }}>Fetching consensus details...</div>
            ) : (
              <div className="detail-layout">
                {/* Main Content Column */}
                <div>
                  <button 
                    onClick={handleBack} 
                    style={{ background: 'transparent', border: 'none', color: 'var(--accent-primary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '24px', fontWeight: 600 }}
                  >
                    ← Back to Catalog
                  </button>

                  <div className="detail-main-header">
                    <h1 className="detail-main-title">{articleDetail.title}</h1>
                    <div className="detail-meta-row">
                      <span>🏷️ {articleDetail.category.name}</span>
                      <span>📅 {new Date(articleDetail.published_at).toLocaleDateString()}</span>
                      <span>👁️ {articleDetail.view_count} views</span>
                    </div>
                  </div>

                  {/* Tabs */}
                  <div className="detail-tab-menu">
                    <button 
                      className={`detail-tab ${activeTab === "guide" ? "active" : ""}`}
                      onClick={() => setActiveTab("guide")}
                    >
                      Consensus Review
                    </button>
                    <button 
                      className={`detail-tab ${activeTab === "proscons" ? "active" : ""}`}
                      onClick={() => setActiveTab("proscons")}
                    >
                      Pros & Cons
                    </button>
                    <button 
                      className={`detail-tab ${activeTab === "specs" ? "active" : ""}`}
                      onClick={() => setActiveTab("specs")}
                    >
                      Specs
                    </button>
                  </div>

                  {/* Tab Panels */}
                  <div style={{ minHeight: '400px' }}>
                    {activeTab === "guide" && (
                      <div 
                        className="article-body-html" 
                        dangerouslySetInnerHTML={{ __html: articleDetail.full_article_html }} 
                      />
                    )}

                    {activeTab === "proscons" && (
                      <div className="pros-cons-container" style={{ margin: 0 }}>
                        {articleDetail.products.map(product => (
                          <div key={product.id} className="pros-cons-container" style={{ gridTemplateColumns: '1fr 1fr', gap: '30px', width: '100%' }}>
                            <div className="pro-con-box" style={{ background: 'rgba(255,255,255,0.01)' }}>
                              <h3 className="pro-con-header pros" style={{ fontSize: '16px' }}>🟢 Pros</h3>
                              <div className="pro-con-list">
                                {product.pros?.map((p, i) => (
                                  <div key={i} className="pro-con-item pro">
                                    <span className="pro-con-text">{p.text}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                            <div className="pro-con-box" style={{ background: 'rgba(255,255,255,0.01)' }}>
                              <h3 className="pro-con-header cons" style={{ fontSize: '16px' }}>🔴 Cons</h3>
                              <div className="pro-con-list">
                                {product.cons?.map((c, i) => (
                                  <div key={i} className="pro-con-item con">
                                    <span className="pro-con-text">{c.text}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {activeTab === "specs" && (
                      <div className="specs-grid">
                        {articleDetail.products.map(product => 
                          Object.entries(product.specs || {}).map(([key, val]) => (
                            <div key={key} className="spec-item">
                              <div className="spec-key">{key}</div>
                              <div className="spec-val">{String(val)}</div>
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Sidebar Column */}
                <aside>
                  <div className="sidebar-card">
                    {articleDetail.products[0]?.image_url && (
                      <img 
                        src={articleDetail.products[0].image_url} 
                        alt={articleDetail.products[0].name} 
                        style={{ width: '100%', borderRadius: '12px', marginBottom: '20px', objectFit: 'cover', border: '1px solid var(--border-glow)' }} 
                      />
                    )}

                    <div className="badge-rating">
                      ⭐ {articleDetail.products[0]?.rating || "4.5"} / 5.0 Rating
                    </div>
                    
                    <h3 className="sidebar-summary-title">Summary Verdict</h3>
                    <p className="sidebar-summary-text">{articleDetail.introduction}</p>

                    {articleDetail.products.map(product => 
                      product.affiliate_links?.map(link => (
                        <div key={link.id}>
                          <button 
                            className="buy-button"
                            onClick={() => handleAffiliateClick(link.id, link.tracked_url)}
                          >
                            Buy on {link.platform.toUpperCase()} 🛒
                          </button>
                        </div>
                      ))
                    )}
                    <p className="buy-button-sub">Commissions earned support the editorial team.</p>
                  </div>
                </aside>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default App;
