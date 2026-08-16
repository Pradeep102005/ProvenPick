import { useState, useEffect } from 'react';

const API_BASE = "/api/articles";

const L1_CATEGORIES_LIST = [
  "All",
  "Electronics",
  "Computer Accessories",
  "Audio",
  "Home Appliances",
  "Kitchen Appliances",
  "Gaming",
  "Smart Home",
  "Networking",
  "Wearables",
  "Office / Productivity",
  "Others"
];

function App() {
  const [articles, setArticles] = useState([]);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [articleDetail, setArticleDetail] = useState(null);
  const [activeTab, setActiveTab] = useState("guide");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState(null);

  const [categoriesTree, setCategoriesTree] = useState([]);
  const [selectedL1, setSelectedL1] = useState("All");
  const [selectedL2, setSelectedL2] = useState("All");

  const [bestIndex, setBestIndex] = useState(0);

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

  const fetchArticles = async () => {
    setLoading(true);
    try {
      const res = await fetch(API_BASE);
      if (!res.ok) throw new Error("Failed to load buying guides.");
      const data = await res.json();
      setArticles(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCategorySelect = (cat) => {
    setSelectedL1(cat);
    setSelectedL2("All");
    if (cat === "All") {
      window.history.pushState({}, "", "/");
    } else {
      const slug = cat.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
      window.history.pushState({}, "", `/${slug}`);
    }
    if (selectedArticle) handleBack();
  };

  useEffect(() => {
    const path = window.location.pathname.replace(/^\//, '').toLowerCase();
    if (path) {
      const matchedCat = L1_CATEGORIES_LIST.find(c => 
        c.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') === path
      );
      if (matchedCat) {
        setSelectedL1(matchedCat);
      }
    }
    fetchArticles();
    fetchCategories();
  }, []);

  const loadArticleDetail = async (slug) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/${slug}`);
      if (!res.ok) throw new Error("Failed to load review details.");
      const data = await res.json();
      setArticleDetail(data);
      setActiveTab("guide");
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
      console.error("Failed to register affiliate click", err);
    }
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const currentL1Obj = categoriesTree.find(c => c.name.toLowerCase() === selectedL1.toLowerCase());
  const l2Subcategories = currentL1Obj ? currentL1Obj.l2_categories : [];

  const filteredArticles = articles.filter(a => {
    const catName = (a.category_name || "").toLowerCase();
    const titleText = (a.title || "").toLowerCase();
    
    if (selectedL1 === "All") return true;
    
    const l1Target = selectedL1.toLowerCase();
    const l2Target = selectedL2.toLowerCase();
    
    if (selectedL2 !== "All") {
      return catName.includes(l2Target) || titleText.includes(l2Target);
    }
    
    return catName.includes(l1Target) || titleText.includes(l1Target) ||
      l2Subcategories.some(l2 => catName.includes(l2.name.toLowerCase()));
  });

  const bestCarouselItems = L1_CATEGORIES_LIST.filter(c => c !== "All").map(catName => {
    const matched = articles.find(a => {
      const cn = (a.category_name || "").toLowerCase();
      const tt = (a.title || "").toLowerCase();
      return cn.includes(catName.toLowerCase()) || tt.includes(catName.toLowerCase());
    });
    return {
      category: catName,
      article: matched || articles[0]
    };
  }).filter(item => item.article);

  const currentBestItem = bestCarouselItems[bestIndex % (bestCarouselItems.length || 1)];

  const handleNextBest = () => {
    setBestIndex((prev) => (prev + 1) % (bestCarouselItems.length || 1));
  };

  const handlePrevBest = () => {
    setBestIndex((prev) => (prev - 1 + bestCarouselItems.length) % (bestCarouselItems.length || 1));
  };

  return (
    <div className="site-wrapper" style={{ background: '#090a0f', color: '#f3f4f6', minHeight: '100vh', width: '100%' }}>
      {/* Top Banner */}
      <div className="cnet-top-banner" style={{ background: '#d9f99d', color: '#111827', padding: '8px 24px', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '13px' }}>
        <div>
          <span style={{ background: '#111827', color: '#d9f99d', padding: '2px 8px', borderRadius: '4px', marginRight: '8px', fontSize: '11px' }}>PROVENPICK</span>
          NAVIGATING A WORLD OF ACCELERATING CHANGE
        </div>
        <div>⚡ EXPERT TESTED & VERIFIED</div>
      </div>

      {/* Header */}
      <header className="cnet-header-dark" style={{ background: '#0f172a', borderBottom: '1px solid #1e293b', padding: '14px 0' }}>
        <div className="cnet-container" style={{ maxWidth: '1400px', margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div 
            style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '12px' }} 
            onClick={() => { setSelectedL1("All"); setSelectedL2("All"); handleBack(); }}
          >
            <div style={{ background: '#6366f1', color: '#fff', fontWeight: '900', padding: '8px 16px', borderRadius: '6px', fontSize: '20px', letterSpacing: '1px' }}>
              PROVENPICK
            </div>
          </div>

          <nav className="cnet-nav-categories" style={{ display: 'flex', gap: '18px', overflowX: 'auto', padding: '4px 0' }}>
            {L1_CATEGORIES_LIST.map(cat => (
              <span
                key={cat}
                style={{
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: selectedL1 === cat ? 'bold' : '500',
                  color: selectedL1 === cat ? '#a3e635' : '#cbd5e1',
                  whiteSpace: 'nowrap',
                  paddingBottom: '4px',
                  borderBottom: selectedL1 === cat ? '2px solid #a3e635' : 'none'
                }}
                onClick={() => handleCategorySelect(cat)}
              >
                {cat}
              </span>
            ))}
          </nav>
        </div>

        {l2Subcategories.length > 0 && (
          <div style={{ background: '#090a0f', borderTop: '1px solid #1e293b', padding: '10px 0' }}>
            <div className="cnet-container" style={{ maxWidth: '1400px', margin: '0 auto', padding: '0 24px', display: 'flex', gap: '10px', overflowX: 'auto' }}>
              <button 
                style={{ background: selectedL2 === 'All' ? '#6366f1' : '#1e293b', color: '#fff', border: 'none', padding: '6px 14px', borderRadius: '20px', fontSize: '13px', cursor: 'pointer', whiteSpace: 'nowrap' }}
                onClick={() => { setSelectedL2("All"); if (selectedArticle) handleBack(); }}
              >
                All {selectedL1} →
              </button>
              {l2Subcategories.map(l2 => (
                <button 
                  key={l2.id} 
                  style={{ background: selectedL2 === l2.name ? '#6366f1' : '#1e293b', color: '#fff', border: 'none', padding: '6px 14px', borderRadius: '20px', fontSize: '13px', cursor: 'pointer', whiteSpace: 'nowrap' }}
                  onClick={() => { setSelectedL2(l2.name); if (selectedArticle) handleBack(); }}
                >
                  {l2.name} →
                </button>
              ))}
            </div>
          </div>
        )}
      </header>

      {/* Main Body */}
      <div className="cnet-container" style={{ maxWidth: '1400px', margin: '0 auto', padding: '32px 24px' }}>
        {selectedArticle ? (
          /* Article Detail View */
          <div>
            <button 
              onClick={handleBack} 
              style={{ background: '#1e293b', color: '#fff', border: 'none', padding: '8px 18px', borderRadius: '6px', cursor: 'pointer', marginBottom: '24px' }}
            >
              ← Back to {selectedL1 === 'All' ? 'Home' : selectedL1}
            </button>

            {detailLoading ? (
              <div style={{ padding: '60px 0', textAlign: 'center', color: '#94a3b8' }}>Loading detailed review...</div>
            ) : articleDetail ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '40px' }}>
                <div>
                  <span style={{ color: '#a3e635', fontSize: '13px', fontWeight: 'bold', textTransform: 'uppercase' }}>
                    {articleDetail.category_name}
                  </span>
                  <h1 style={{ fontSize: '36px', color: '#fff', marginTop: '8px', marginBottom: '16px', lineHeight: '1.2' }}>
                    {articleDetail.title}
                  </h1>
                  <p style={{ fontSize: '18px', color: '#cbd5e1', lineHeight: '1.6', marginBottom: '24px' }}>
                    {articleDetail.introduction}
                  </p>

                  <div style={{ background: '#1e293b', padding: '24px', borderRadius: '12px', marginBottom: '32px' }}>
                    <div style={{ display: 'flex', gap: '16px', marginBottom: '20px' }}>
                      {["guide", "proscons", "specs"].map(tab => (
                        <button
                          key={tab}
                          style={{
                            background: activeTab === tab ? '#6366f1' : 'transparent',
                            color: '#fff',
                            border: 'none',
                            padding: '8px 16px',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            fontWeight: 'bold'
                          }}
                          onClick={() => setActiveTab(tab)}
                        >
                          {tab === 'guide' ? 'Full Guide' : tab === 'proscons' ? 'Pros & Cons' : 'Specifications'}
                        </button>
                      ))}
                    </div>

                    {activeTab === 'guide' && (
                      <div 
                        dangerouslySetInnerHTML={{ __html: articleDetail.full_article_html }} 
                        style={{ color: '#e2e8f0', lineHeight: '1.8' }} 
                      />
                    )}

                    {activeTab === 'proscons' && articleDetail.products?.[0] && (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
                        {/* Pros Card */}
                        <div style={{ background: 'rgba(52, 211, 153, 0.05)', border: '1px solid rgba(52, 211, 153, 0.3)', borderRadius: '16px', padding: '24px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
                            <div style={{ background: '#10b981', color: '#042f2e', width: '28px', height: '28px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>✓</div>
                            <h4 style={{ color: '#34d399', fontSize: '18px', fontWeight: 'bold', margin: 0 }}>PROS</h4>
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            {articleDetail.products[0].pros?.map((p, i) => (
                              <div key={i} style={{ background: 'rgba(255, 255, 255, 0.03)', borderLeft: '3px solid #34d399', padding: '12px 16px', borderRadius: '8px', color: '#ecfdf5', fontSize: '14px', lineHeight: '1.5' }}>
                                {typeof p === 'string' ? p : p.text}
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Cons Card */}
                        <div style={{ background: 'rgba(248, 113, 113, 0.05)', border: '1px solid rgba(248, 113, 113, 0.3)', borderRadius: '16px', padding: '24px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
                            <div style={{ background: '#ef4444', color: '#450a0a', width: '28px', height: '28px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>✕</div>
                            <h4 style={{ color: '#f87171', fontSize: '18px', fontWeight: 'bold', margin: 0 }}>CONS</h4>
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            {articleDetail.products[0].cons?.map((c, i) => (
                              <div key={i} style={{ background: 'rgba(255, 255, 255, 0.03)', borderLeft: '3px solid #f87171', padding: '12px 16px', borderRadius: '8px', color: '#fef2f2', fontSize: '14px', lineHeight: '1.5' }}>
                                {typeof c === 'string' ? c : c.text}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}

                    {activeTab === 'specs' && articleDetail.products?.[0] && (
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <tbody>
                          {Object.entries(articleDetail.products[0].specs || {}).map(([k, v]) => (
                            <tr key={k} style={{ borderBottom: '1px solid #334155' }}>
                              <td style={{ padding: '10px', color: '#94a3b8', width: '200px' }}>{k}</td>
                              <td style={{ padding: '10px', color: '#fff' }}>{String(v)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>

                {/* Right Sticky Product Card */}
                {articleDetail.products?.[0] && (
                  <div>
                    <div style={{ background: '#1e293b', borderRadius: '12px', padding: '24px', position: 'sticky', top: '20px' }}>
                      <img 
                        src={articleDetail.products[0].image_url || "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600"} 
                        alt={articleDetail.products[0].name} 
                        style={{ width: '100%', borderRadius: '8px', height: '220px', objectFit: 'cover', marginBottom: '16px' }}
                      />
                      <h3 style={{ fontSize: '20px', color: '#fff' }}>{articleDetail.products[0].name}</h3>
                      <p style={{ color: '#94a3b8', marginBottom: '16px' }}>{articleDetail.products[0].brand}</p>
                      
                      {articleDetail.products[0].affiliate_links?.map((link, idx) => (
                        <button
                          key={idx}
                          style={{ width: '100%', background: '#a3e635', color: '#111827', border: 'none', padding: '12px', borderRadius: '8px', fontWeight: 'bold', cursor: 'pointer', marginBottom: '10px' }}
                          onClick={() => handleAffiliateClick(link.id, link.tracked_url)}
                        >
                          Check Price on {link.platform?.toUpperCase()} →
                        </button>
                      ))}

                      <p style={{ fontSize: '11px', color: '#94a3b8', marginTop: '12px', lineHeight: '1.4', textAlign: 'center', fontStyle: 'italic' }}>
                        ⚡ If you purchase through links on our site, we may earn an affiliate commission at no extra cost to you.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        ) : (
          /* Homepage View */
          <>
            {selectedL1 === "All" && currentBestItem && currentBestItem.article ? (
              <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '24px', marginBottom: '48px' }}>
                <div style={{ background: '#fef08a', color: '#111827', borderRadius: '16px', padding: '28px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontSize: '32px', fontWeight: '900', letterSpacing: '1px' }}>BEST</div>
                    <p style={{ fontSize: '13px', color: '#4b5563', marginTop: '4px', marginBottom: '24px' }}>
                      Top rated picks from each category
                    </p>
                    
                    <div style={{ background: '#111827', color: '#fef08a', padding: '8px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 'bold', display: 'inline-block', marginBottom: '12px' }}>
                      CATEGORY: {currentBestItem.category.toUpperCase()}
                    </div>
                    <h4 style={{ fontSize: '15px', color: '#111827', lineHeight: '1.4' }}>
                      Best {currentBestItem.category} for 2026: Tested & Reviewed
                    </h4>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '24px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#4b5563' }}>
                      {bestIndex + 1} of {bestCarouselItems.length} Categories
                    </span>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button 
                        onClick={handlePrevBest}
                        style={{ background: '#111827', color: '#fff', border: 'none', width: '36px', height: '36px', borderRadius: '50%', cursor: 'pointer', fontSize: '16px' }}
                      >
                        ‹
                      </button>
                      <button 
                        onClick={handleNextBest}
                        style={{ background: '#111827', color: '#fff', border: 'none', width: '36px', height: '36px', borderRadius: '50%', cursor: 'pointer', fontSize: '16px' }}
                      >
                        ›
                      </button>
                    </div>
                  </div>
                </div>

                <div 
                  style={{ background: '#1e293b', borderRadius: '16px', overflow: 'hidden', display: 'grid', gridTemplateColumns: '1fr 1fr', cursor: 'pointer' }}
                  onClick={() => handleSelectArticle(currentBestItem.article.slug)}
                >
                  <img 
                    src={currentBestItem.article.products?.[0]?.image_url || "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=800"} 
                    alt={currentBestItem.article.title}
                    style={{ width: '100%', height: '380px', objectFit: 'cover' }}
                  />
                  <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <span style={{ color: '#a3e635', fontSize: '12px', fontWeight: 'bold', textTransform: 'uppercase' }}>
                      FEATURED PICK
                    </span>
                    <h2 style={{ fontSize: '26px', color: '#fff', marginTop: '8px', marginBottom: '16px', lineHeight: '1.3' }}>
                      {currentBestItem.article.title}
                    </h2>
                    <p style={{ color: '#cbd5e1', fontSize: '14px', lineHeight: '1.6', marginBottom: '20px' }}>
                      {currentBestItem.article.introduction || currentBestItem.article.summary}
                    </p>
                    <span style={{ color: '#a3e635', fontWeight: 'bold', fontSize: '14px' }}>Read Full Review →</span>
                  </div>
                </div>
              </div>
            ) : null}

            {selectedL1 !== "All" && (
              <div style={{ marginBottom: '24px', borderBottom: '1px solid #1e293b', paddingBottom: '16px' }}>
                <h2 style={{ fontSize: '28px', color: '#fff' }}>
                  {selectedL1} {selectedL2 !== "All" ? `> ${selectedL2}` : ''} ({filteredArticles.length} Guides)
                </h2>
              </div>
            )}

            <section style={{ marginTop: '32px' }}>
              <h3 style={{ fontSize: '22px', color: '#fff', marginBottom: '20px', borderBottom: '2px solid #a3e635', paddingBottom: '8px', display: 'inline-block' }}>
                {selectedL1 === "All" ? "LATEST HANDS-ON BUYING GUIDES" : `${selectedL1.toUpperCase()} REVIEWS`}
              </h3>

              {loading ? (
                <div style={{ padding: '40px 0', textAlign: 'center', color: '#94a3b8' }}>Loading published reviews...</div>
              ) : filteredArticles.length === 0 ? (
                <div style={{ padding: '40px', background: '#1e293b', borderRadius: '12px', textAlign: 'center', color: '#94a3b8' }}>
                  No published reviews found for {selectedL1} {selectedL2 !== "All" ? `> ${selectedL2}` : ''} yet. Approve drafts in Editor Dashboard to populate this section!
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '24px' }}>
                  {filteredArticles.map((art) => (
                    <div 
                      key={art.id} 
                      style={{ background: '#1e293b', borderRadius: '12px', overflow: 'hidden', cursor: 'pointer', transition: 'transform 0.2s', border: '1px solid #334155' }}
                      onClick={() => handleSelectArticle(art.slug)}
                    >
                      <img 
                        src={art.products?.[0]?.image_url || "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600"} 
                        alt={art.title}
                        style={{ width: '100%', height: '200px', objectFit: 'cover' }}
                      />
                      <div style={{ padding: '20px' }}>
                        <span style={{ color: '#a3e635', fontSize: '11px', fontWeight: 'bold', textTransform: 'uppercase' }}>
                          {art.category_name}
                        </span>
                        <h4 style={{ fontSize: '18px', color: '#fff', marginTop: '6px', marginBottom: '10px', lineHeight: '1.4' }}>
                          {art.title}
                        </h4>
                        <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: '1.5', height: '40px', overflow: 'hidden' }}>
                          {art.introduction || art.summary}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}

export default App;
