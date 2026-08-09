import { useState, useEffect } from 'react';

const API_BASE = "/api/articles";

function App() {
  const [articles, setArticles] = useState([]);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [articleDetail, setArticleDetail] = useState(null);
  const [activeTab, setActiveTab] = useState("guide"); // guide | proscons | specs
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState(null);

  const [categoriesTree, setCategoriesTree] = useState([]);
  const [selectedL1, setSelectedL1] = useState("All");
  const [selectedL2, setSelectedL2] = useState("All");

  // Fetch DB Categories taxonomy
  const fetchCategories = async () => {
    try {
      const res = await fetch("/api/categories");
      if (res.ok) {
        const data = await res.json();
        setCategoriesTree(data);
      }
    } catch (err) {
      console.error("Failed to load DB taxonomy", err);
    }
  };

  // Fetch all published articles from Production API
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
    fetchCategories();
  }, []);

  // Fetch article detail by slug
  const loadArticleDetail = async (slug) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/${slug}`);
      if (!res.ok) throw new Error("Failed to load review details.");
      const data = await res.json();
      setArticleDetail(data);
      setActiveTab("guide");
      
      // Post view count increment
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
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleBack = () => {
    setSelectedArticle(null);
    setArticleDetail(null);
    fetchArticles();
  };

  const handleAffiliateClick = async (linkId, url) => {
    try {
      await fetch(`${API_BASE}/affiliate/click/${linkId}`, { method: "POST" });
    } catch (err) {
      console.error("Failed to register affiliate click event", err);
    }
    window.open(url, "_blank", "noopener,noreferrer");
  };

  // Get current L2 subcategory list based on selected L1
  const currentL1Obj = categoriesTree.find(c => c.name.toLowerCase() === selectedL1.toLowerCase());
  const l2Subcategories = currentL1Obj ? currentL1Obj.l2_categories : [];

  // Filtered articles based on selected L1 and L2
  const filteredArticles = articles.filter(a => {
    const catName = (a.category_name || "").toLowerCase();
    if (selectedL1 === "All") return true;
    
    if (selectedL2 !== "All") {
      return catName.includes(selectedL2.toLowerCase());
    }
    
    // Check if category matches L1 or any of its L2s
    if (catName.includes(selectedL1.toLowerCase())) return true;
    return l2Subcategories.some(l2 => catName.includes(l2.name.toLowerCase()));
  });

  const featuredHeroArticle = filteredArticles[0] || articles[0];
  const sideBestArticles = (filteredArticles.length > 0 ? filteredArticles : articles).slice(0, 5);

  return (
    <div>
      {/* 1. Top CNET Announcement Banner */}
      <div className="cnet-top-banner">
        <div className="cnet-top-banner-title">
          <span className="cnet-banner-badge">PROVENPICK</span>
          NAVIGATING A WORLD OF ACCELERATING CHANGE
        </div>
        <div style={{ fontSize: '13px', cursor: 'pointer' }}>⚡ EXPERT TESTED</div>
      </div>

      {/* 2. CNET Black Navigation Header with DB L1 Categories */}
      <header className="cnet-header-dark">
        <div className="cnet-container">
          <div className="cnet-header-main">
            <div className="cnet-brand" onClick={() => { setSelectedL1("All"); setSelectedL2("All"); handleBack(); }}>
              <div className="cnet-logo-box" style={{ background: '#6366f1' }}>PROVENPICK</div>
              <div className="cnet-tagline">VERIFIED REVIEWS • ZERO AD BIAS</div>
            </div>

            <ul className="cnet-nav-categories">
              <li 
                className={`cnet-nav-item ${selectedL1 === 'All' ? 'active' : ''}`}
                onClick={() => { setSelectedL1("All"); setSelectedL2("All"); if (selectedArticle) handleBack(); }}
              >
                All
              </li>
              {categoriesTree.map(l1 => (
                <li 
                  key={l1.id} 
                  className={`cnet-nav-item ${selectedL1 === l1.name ? 'active' : ''}`}
                  onClick={() => { setSelectedL1(l1.name); setSelectedL2("All"); if (selectedArticle) handleBack(); }}
                >
                  {l1.name}
                </li>
              ))}
            </ul>

            <div className="cnet-header-actions">
              <div className="google-preferred-btn">
                <span>G</span> Add as preferred source on Google
              </div>
            </div>
          </div>
        </div>

        {/* L2 Subcategory Pills Bar */}
        <div className="cnet-subnav-bar">
          <div className="cnet-container cnet-subnav-flex">
            <button 
              className={`cnet-pill ${selectedL2 === 'All' ? 'active' : ''}`}
              onClick={() => { setSelectedL2("All"); if (selectedArticle) handleBack(); }}
            >
              All {selectedL1 !== "All" ? selectedL1 : "Categories"} →
            </button>
            {l2Subcategories.map(l2 => (
              <button 
                key={l2.id} 
                className={`cnet-pill ${selectedL2 === l2.name ? 'active' : ''}`}
                onClick={() => { setSelectedL2(l2.name); if (selectedArticle) handleBack(); }}
              >
                {l2.name} →
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="cnet-container">
        {!selectedArticle ? (
          <>
            {/* CNET Editorial Hero Layout */}
            <div className="cnet-hero-grid">
              {/* Left Column: Yellow "BEST" Sidebar Box */}
              <div className="cnet-best-box">
                <div className="cnet-best-header">
                  <div className="cnet-best-title">BEST</div>
                  <div className="cnet-best-subtitle">Editors' picks and our top buying guides</div>
                </div>

                <div className="cnet-best-list">
                  {sideBestArticles.length > 0 ? (
                    sideBestArticles.map((art, idx) => (
                      <span key={art.id || idx} className="cnet-best-item" onClick={() => handleSelectArticle(art.slug)}>
                        Best {art.name || art.category_name} for 2026: Expert Tested & Reviewed
                      </span>
                    ))
                  ) : (
                    <>
                      <span className="cnet-best-item">Best Smartphones for 2026: Top Tested Picks</span>
                      <span className="cnet-best-item">Best Flagship Performance Phones</span>
                      <span className="cnet-best-item">Best Value Audio Devices</span>
                      <span className="cnet-best-item">Best Battery Life Phones Tested</span>
                    </>
                  )}
                </div>
              </div>

              {/* Center/Right Big Hero Feature Card */}
              {featuredHeroArticle ? (
                <div className="cnet-hero-main-card" onClick={() => handleSelectArticle(featuredHeroArticle.slug)}>
                  <div className="cnet-hero-img-box">
                    <img 
                      src={featuredHeroArticle.products?.[0]?.image_url || featuredHeroArticle.products?.[0]?.image_urls?.[0] || "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop&q=80"} 
                      alt={featuredHeroArticle.title} 
                      className="cnet-hero-img"
                    />
                  </div>
                  <div className="cnet-hero-content">
                    <div className="cnet-hero-headline">{featuredHeroArticle.title}</div>
                    <div className="cnet-hero-summary">{featuredHeroArticle.introduction}</div>
                    <div className="cnet-byline">By Editorial Team • 5 Min Read</div>
                  </div>
                </div>
              ) : (
                <div className="cnet-hero-main-card" style={{ gridColumn: 'span 2', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '300px' }}>
                  <div style={{ textAlign: 'center', color: '#777' }}>
                    No published articles yet. Generating fresh articles from Scout Agent...
                  </div>
                </div>
              )}
            </div>

            {/* Horizontal Flash Card Carousel Section: Trending Product Reviews */}
            <div className="cnet-section-header">
              <div className="cnet-section-title">Trending Product Reviews</div>
              <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--cnet-red)', cursor: 'pointer' }}>View All →</div>
            </div>

            {loading ? (
              <div style={{ textAlign: 'center', padding: '60px', color: '#777' }}>Loading reviews catalog...</div>
            ) : error ? (
              <div style={{ color: 'red', textAlign: 'center', padding: '40px' }}>Error loading guides: {error}</div>
            ) : filteredArticles.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px', color: '#888' }}>
                No buying guides published yet. Publish a draft from Editor Dashboard to see it live!
              </div>
            ) : (
              <div className="cnet-carousel-container">
                {filteredArticles.map(art => {
                  const firstProd = art.products?.[0] || {};
                  const mainImg = firstProd.image_url || firstProd.image_urls?.[0] || "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop&q=80";
                  return (
                    <div key={art.id} className="cnet-flash-card" onClick={() => handleSelectArticle(art.slug)}>
                      <div className="cnet-flash-img-box">
                        <img src={mainImg} alt={art.title} className="cnet-flash-img" />
                        <div className="cnet-rating-badge">⭐ {firstProd.rating || "4.5"}</div>
                      </div>
                      <div className="cnet-flash-body">
                        <div className="cnet-flash-category">{art.category_name || "Mobile"}</div>
                        <div className="cnet-flash-title">{art.title}</div>
                        <div className="cnet-flash-byline">By ProvenPick Experts</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Additional Horizontal Section: Top Tested Smartphones */}
            <div className="cnet-section-header" style={{ marginTop: '50px' }}>
              <div className="cnet-section-title">Latest Hands-On Buying Guides</div>
            </div>

            <div className="cnet-carousel-container" style={{ marginBottom: '60px' }}>
              {articles.map(art => {
                const firstProd = art.products?.[0] || {};
                const mainImg = firstProd.image_urls?.[1] || firstProd.image_urls?.[0] || "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=600&auto=format&fit=crop&q=80";
                return (
                  <div key={`guide-${art.id}`} className="cnet-flash-card" onClick={() => handleSelectArticle(art.slug)}>
                    <div className="cnet-flash-img-box">
                      <img src={mainImg} alt={art.title} className="cnet-flash-img" />
                      <div className="cnet-rating-badge">₹{firstProd.price_inr || "39,999"}</div>
                    </div>
                    <div className="cnet-flash-body">
                      <div className="cnet-flash-category">{firstProd.brand || "Tech"}</div>
                      <div className="cnet-flash-title">{art.title}</div>
                      <div className="cnet-flash-byline">Consensus Score: {firstProd.rating || "4.5"}/5</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          /* Article Detail View (CNET Light Mode Page) */
          <>
            {detailLoading || !articleDetail ? (
              <div style={{ textAlign: 'center', padding: '80px', color: '#777' }}>Loading article details...</div>
            ) : (
              <div>
                {/* Back Button */}
                <div style={{ margin: '24px 0 12px' }}>
                  <span 
                    onClick={handleBack} 
                    style={{ cursor: 'pointer', fontWeight: '800', fontSize: '13px', color: 'var(--cnet-red)', textTransform: 'uppercase' }}
                  >
                    ← Back to ProvenPick Home
                  </span>
                </div>

                {/* Article Header */}
                <div className="cnet-detail-header">
                  <h1 className="cnet-detail-title">{articleDetail.title}</h1>
                  
                  <div className="cnet-meta-strip">
                    <span>By <strong>ProvenPick Editorial Staff</strong></span>
                    <span>•</span>
                    <span>Category: <strong>{articleDetail.category.name}</strong></span>
                    <span>•</span>
                    <span>Published: {new Date(articleDetail.published_at).toLocaleDateString()}</span>
                    <span>•</span>
                    <span>👁️ {articleDetail.view_count} views</span>
                  </div>
                </div>

                {/* Main Article Grid */}
                <div className="cnet-detail-grid">
                  {/* Left Column: Product Photos, Tabs, Review Content */}
                  <div>
                    {/* Product Photo Gallery */}
                    {articleDetail.products[0]?.image_urls?.length > 0 && (
                      <div className="cnet-gallery-box">
                        <img 
                          src={articleDetail.products[0].image_urls[0]} 
                          alt="Product" 
                          className="cnet-gallery-main-img"
                        />
                        <div className="cnet-gallery-sub-grid">
                          <img 
                            src={articleDetail.products[0].image_urls[1] || articleDetail.products[0].image_urls[0]} 
                            alt="Angle 2" 
                            className="cnet-gallery-sub-img"
                          />
                          <img 
                            src={articleDetail.products[0].image_urls[2] || articleDetail.products[0].image_urls[0]} 
                            alt="Angle 3" 
                            className="cnet-gallery-sub-img"
                          />
                        </div>
                      </div>
                    )}

                    {/* CNET Section Tabs */}
                    <div className="cnet-tab-bar">
                      <button 
                        className={`cnet-tab-btn ${activeTab === 'guide' ? 'active' : ''}`}
                        onClick={() => setActiveTab('guide')}
                      >
                        Consensus Review
                      </button>
                      <button 
                        className={`cnet-tab-btn ${activeTab === 'proscons' ? 'active' : ''}`}
                        onClick={() => setActiveTab('proscons')}
                      >
                        Pros & Cons
                      </button>
                      <button 
                        className={`cnet-tab-btn ${activeTab === 'specs' ? 'active' : ''}`}
                        onClick={() => setActiveTab('specs')}
                      >
                        Specifications
                      </button>
                    </div>

                    {/* Tab Panels */}
                    {activeTab === 'guide' && (
                      <div 
                        className="cnet-article-body"
                        dangerouslySetInnerHTML={{ __html: articleDetail.full_article_html }}
                      />
                    )}

                    {activeTab === 'proscons' && (
                      <div className="cnet-pros-cons-card">
                        <div className="cnet-pros-cons-header">
                          <div>{articleDetail.products[0]?.name || "Product"} — PROS & CONS</div>
                          <div style={{ fontSize: '13px', color: 'var(--cnet-lime)' }}>CONSENSUS VERDICT</div>
                        </div>

                        <div className="cnet-pros-cons-grid">
                          {/* PROS Column */}
                          <div className="cnet-pros-column">
                            <div className="cnet-pros-title">
                              <span className="cnet-pro-icon">✓</span>
                              THE GOOD (PROS)
                            </div>
                            {articleDetail.products[0]?.pros?.map((p, i) => (
                              <div key={i} className="cnet-pro-con-item">
                                <span className="cnet-pro-icon">✓</span>
                                <div>{p.text}</div>
                              </div>
                            ))}
                          </div>

                          {/* CONS Column */}
                          <div className="cnet-cons-column">
                            <div className="cnet-cons-title">
                              <span className="cnet-con-icon">✕</span>
                              THE BAD (CONS)
                            </div>
                            {articleDetail.products[0]?.cons?.map((c, i) => (
                              <div key={i} className="cnet-pro-con-item">
                                <span className="cnet-con-icon">✕</span>
                                <div>{c.text}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}

                    {activeTab === 'specs' && (
                      <div className="cnet-specs-table-box">
                        <table className="cnet-specs-table">
                          <thead>
                            <tr>
                              <th>Feature Specification</th>
                              <th>Details</th>
                            </tr>
                          </thead>
                          <tbody>
                            {articleDetail.products.map(product => 
                              Object.entries(product.specs || {}).map(([key, val]) => (
                                <tr key={key}>
                                  <td className="cnet-spec-key">{key}</td>
                                  <td className="cnet-spec-val">{String(val)}</td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  {/* Right Column: Sticky Score & Buy Box */}
                  <aside>
                    <div className="cnet-sidebar-card">
                      <div className="cnet-score-box">
                        <div className="cnet-score-num">
                          {articleDetail.products[0]?.rating || "4.5"}
                        </div>
                        <div className="cnet-score-label">PROVENPICK CONSENSUS SCORE</div>
                      </div>

                      <div style={{ marginBottom: '20px' }}>
                        <div style={{ fontSize: '12px', fontWeight: '800', textTransform: 'uppercase', color: '#777', marginBottom: '4px' }}>
                          MSRP / STARTING PRICE
                        </div>
                        <div style={{ fontSize: '28px', fontWeight: '900', color: '#111' }}>
                          ₹{articleDetail.products[0]?.price_inr || "39,999"}
                        </div>
                      </div>

                      {articleDetail.products.map(product => 
                        product.affiliate_links?.map(link => (
                          <button 
                            key={link.id} 
                            className="cnet-buy-btn"
                            onClick={() => handleAffiliateClick(link.id, link.tracked_url)}
                          >
                            CHECK PRICE ON {link.platform.toUpperCase()} 🛒
                          </button>
                        ))
                      )}

                      <div style={{ fontSize: '11px', color: '#888', textAlign: 'center', marginTop: '12px', lineHeight: '1.4' }}>
                        When you buy through links on our site, we may earn an affiliate commission.
                      </div>
                    </div>
                  </aside>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default App;
