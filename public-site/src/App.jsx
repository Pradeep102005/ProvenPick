import { useState, useEffect, useRef } from 'react';

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

const L2_TAXONOMY_MAP = {
  "Electronics": ["Smartphones", "Laptops", "Tablets", "Monitors", "TVs", "Cameras", "Printers"],
  "Computer Accessories": ["Keyboards", "Mice", "Headsets", "Webcams", "USB Hubs"],
  "Audio": ["Wireless Earbuds", "Headphones", "Soundbars", "Bluetooth Speakers"],
  "Home Appliances": ["Refrigerators", "Washing Machines", "Air Conditioners", "Air Purifiers", "Vacuum Cleaners"],
  "Kitchen Appliances": ["Mixer Grinders", "Microwaves", "Air Fryers", "Coffee Makers", "Electric Kettles", "Rice Cookers"],
  "Gaming": ["Consoles", "Gaming PCs", "Gaming Chairs", "Controllers", "VR"],
  "Smart Home": ["Smart Lights", "Security Cameras", "Smart Locks", "Doorbells", "Plugs"],
  "Networking": ["Routers", "Mesh Systems", "Switches"],
  "Wearables": ["Smartwatches", "Fitness Bands", "Smart Rings"],
  "Office / Productivity": ["Chairs", "Standing Desks", "Desk Lamps"],
  "Others": []
};

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

  const [searchQuery, setSearchQuery] = useState("");
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);
  const searchRef = useRef(null);

  const [showSubModal, setShowSubModal] = useState(false);
  const [subName, setSubName] = useState("");
  const [subEmail, setSubEmail] = useState("");
  const [subIncludeL1, setSubIncludeL1] = useState(true);
  const [subLoading, setSubLoading] = useState(false);
  const [subMsg, setSubMsg] = useState(null);

  const handleSubscribeSubmit = async (e) => {
    e.preventDefault();
    if (!subEmail.trim() || !subName.trim()) return;
    setSubLoading(true);
    setSubMsg(null);
    try {
      const catParts = (articleDetail?.category_name || "Electronics -> General Tech").split("->").map(s => s.trim());
      const l1Val = catParts[0] || selectedL1;
      const l2Val = catParts[1] || selectedL2;

      const res = await fetch("/api/subscriptions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: subName.trim(),
          email: subEmail.trim(),
          l1_category: l1Val,
          l2_category: l2Val
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Subscription failed.");
      setSubMsg(data.message || "Subscribed successfully!");
      setTimeout(() => {
        setShowSubModal(false);
        setSubMsg(null);
        setSubName("");
        setSubEmail("");
      }, 2500);
    } catch (err) {
      setSubMsg(`⚠️ ${err.message}`);
    } finally {
      setSubLoading(false);
    }
  };

  const [bestIndex, setBestIndex] = useState(0);

  const fetchCategories = async () => {
    try {
      const res = await fetch("/api/categories");
      if (res.ok) {
        const data = await res.json();
        setCategoriesTree(Array.isArray(data) ? data : []);
      } else {
        setCategoriesTree([]);
      }
    } catch (err) {
      console.error("Failed to load DB taxonomy", err);
      setCategoriesTree([]);
    }
  };

  const fetchArticles = async () => {
    setLoading(true);
    try {
      const res = await fetch(API_BASE);
      if (!res.ok) throw new Error("Failed to load buying guides.");
      const data = await res.json();
      setArticles(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      console.error("Error fetching articles:", err);
      setArticles([]);
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

  const handleSubcategorySelect = (l2Name) => {
    setSelectedL2(l2Name);
    const l1Slug = selectedL1.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
    if (l2Name === "All") {
      window.history.pushState({}, "", `/${l1Slug}`);
    } else {
      const l2Slug = l2Name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
      window.history.pushState({}, "", `/${l1Slug}/${l2Slug}`);
    }
    if (selectedArticle) handleBack();
  };

  useEffect(() => {
    const parts = window.location.pathname.replace(/^\//, '').split('/');
    if (parts[0]) {
      const matchedL1 = L1_CATEGORIES_LIST.find(c => 
        c.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') === parts[0]
      );
      if (matchedL1) {
        setSelectedL1(matchedL1);
        if (parts[1]) {
          const l2List = L2_TAXONOMY_MAP[matchedL1] || [];
          const matchedL2 = l2List.find(l2 => 
            l2.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') === parts[1]
          );
          if (matchedL2) {
            setSelectedL2(matchedL2);
          }
        }
      }
    }
    Promise.all([fetchArticles(), fetchCategories()]).catch(err => console.error("Parallel fetch notice:", err));

    const handleClickOutside = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowSearchDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
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
    setShowSearchDropdown(false);
    setSearchQuery("");
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

  // Safe Arrays
  const safeArticles = Array.isArray(articles) ? articles : [];
  const safeCategoriesTree = Array.isArray(categoriesTree) ? categoriesTree : [];

  // Subcategories for current L1
  const dbL1Obj = safeCategoriesTree.find(c => c && c.name && typeof c.name === 'string' && c.name.toLowerCase() === selectedL1.toLowerCase());
  const dbL2List = dbL1Obj && Array.isArray(dbL1Obj.l2_categories) ? dbL1Obj.l2_categories.map(x => x && x.name ? String(x.name) : "").filter(Boolean) : [];
  const staticL2List = L2_TAXONOMY_MAP[selectedL1] || [];
  const activeL2Subcategories = Array.from(new Set([...dbL2List, ...staticL2List])).filter(Boolean);

  // Search Suggestions matching query
  const searchSuggestions = searchQuery.trim().length > 0 
    ? safeArticles.filter(a => {
        if (!a) return false;
        const q = searchQuery.toLowerCase();
        const t = (a.title || "").toLowerCase();
        const c = (a.category_name || "").toLowerCase();
        const s = (a.summary || "").toLowerCase();
        return t.includes(q) || c.includes(q) || s.includes(q);
      }).slice(0, 6)
    : [];

  // Filtered articles based on Category selection
  const filteredArticles = safeArticles.filter(a => {
    if (!a) return false;
    const catName = (a.category_name || "").toLowerCase();
    const titleText = (a.title || "").toLowerCase();
    
    if (selectedL1 === "All") return true;
    
    const l1Target = selectedL1.toLowerCase();
    const l2Target = selectedL2.toLowerCase();
    
    if (selectedL2 !== "All") {
      return catName.includes(l2Target) || titleText.includes(l2Target);
    }
    
    return catName.includes(l1Target) || titleText.includes(l1Target) ||
      activeL2Subcategories.some(l2 => catName.includes(l2.toLowerCase()));
  });

  const bestCarouselItems = L1_CATEGORIES_LIST.filter(c => c !== "All").map(catName => {
    const matched = safeArticles.find(a => {
      if (!a) return false;
      const cn = (a.category_name || "").toLowerCase();
      const tt = (a.title || "").toLowerCase();
      return cn.includes(catName.toLowerCase()) || tt.includes(catName.toLowerCase());
    });
    return {
      category: catName,
      article: matched || safeArticles[0]
    };
  }).filter(item => item && item.article);

  const currentBestItem = bestCarouselItems.length > 0 ? bestCarouselItems[bestIndex % bestCarouselItems.length] : null;

  return (
    <div className="site-wrapper" style={{ background: '#090a0f', color: '#f3f4f6', minHeight: '100vh', width: '100%' }}>
      {/* Top Announcement Banner */}
      <div className="cnet-top-banner" style={{ background: '#d9f99d', color: '#111827', padding: '8px 24px', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '13px' }}>
        <div>
          <span style={{ background: '#111827', color: '#d9f99d', padding: '2px 8px', borderRadius: '4px', marginRight: '8px', fontSize: '11px' }}>PROVENPICK</span>
          INDEPENDENT CONSENSUS BUYING GUIDES & TECH REVIEWS
        </div>
        <div>⚡ EXPERT TESTED & VERIFIED</div>
      </div>

      {/* Main Header with Spacing & Search Bar */}
      <header className="cnet-header-dark" style={{ background: '#0f172a', borderBottom: '1px solid #1e293b' }}>
        {/* Tier 1: Logo & Search Bar */}
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '16px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '32px' }}>
          {/* Logo */}
          <div 
            style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '12px', minWidth: '180px' }} 
            onClick={() => { setSelectedL1("All"); setSelectedL2("All"); handleBack(); }}
          >
            <div style={{ background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', color: '#fff', fontWeight: '900', padding: '10px 20px', borderRadius: '8px', fontSize: '22px', letterSpacing: '1.5px', boxShadow: '0 4px 14px rgba(99, 102, 241, 0.4)' }}>
              PROVENPICK
            </div>
          </div>

          {/* Autocomplete Search Bar */}
          <div ref={searchRef} style={{ flex: 1, maxWidth: '600px', position: 'relative' }}>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <span style={{ position: 'absolute', left: '16px', color: '#94a3b8', fontSize: '16px' }}>🔍</span>
              <input
                type="text"
                placeholder="Search buying guides (e.g. Samsung, Galaxy S24, LG OLED, Smart Lock)..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setShowSearchDropdown(true);
                }}
                onFocus={() => setShowSearchDropdown(true)}
                style={{
                  width: '100%',
                  background: '#1e293b',
                  border: '1px solid #334155',
                  color: '#fff',
                  padding: '12px 16px 12px 48px',
                  borderRadius: '30px',
                  fontSize: '14px',
                  outline: 'none',
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)'
                }}
              />
              {searchQuery && (
                <button
                  onClick={() => { setSearchQuery(""); setShowSearchDropdown(false); }}
                  style={{ position: 'absolute', right: '16px', background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '14px' }}
                >
                  ✕
                </button>
              )}
            </div>

            {/* Instant Search Suggestions Dropdown */}
            {showSearchDropdown && searchSuggestions.length > 0 && (
              <div 
                style={{
                  position: 'absolute',
                  top: '110%',
                  left: 0,
                  right: 0,
                  background: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '16px',
                  boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
                  zIndex: 9999,
                  overflow: 'hidden',
                  maxHeight: '400px',
                  overflowY: 'auto'
                }}
              >
                <div style={{ padding: '10px 16px', background: '#0f172a', color: '#a3e635', fontSize: '12px', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  Matching Reviews ({searchSuggestions.length})
                </div>
                {searchSuggestions.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => handleSelectArticle(item.slug)}
                    style={{
                      padding: '12px 16px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '14px',
                      cursor: 'pointer',
                      borderBottom: '1px solid rgba(255,255,255,0.05)',
                      transition: 'background 0.2s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = '#334155'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <img 
                      src={item.mindmap_image_url || item.products?.[0]?.image_url || 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=100'} 
                      alt={item.title} 
                      loading="lazy"
                      decoding="async"
                      style={{ width: '48px', height: '48px', objectFit: 'cover', borderRadius: '8px' }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#fff', lineHeight: '1.3' }}>
                        {item.title}
                      </div>
                      <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '3px', display: 'flex', gap: '10px', alignItems: 'center' }}>
                        <span style={{ color: '#a3e635' }}>{item.category_name}</span>
                        {item.products?.[0]?.rating && (
                          <span style={{ color: '#f59e0b' }}>★ {item.products[0].rating}</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Tier 2: Category Navigation Bar */}
        <div style={{ borderTop: '1px solid #1e293b', background: '#0f172a', padding: '10px 0' }}>
          <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '0 24px' }}>
            <nav style={{ display: 'flex', gap: '24px', overflowX: 'auto', paddingBottom: '4px' }}>
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
                    borderBottom: selectedL1 === cat ? '2px solid #a3e635' : 'none',
                    transition: 'color 0.2s'
                  }}
                  onClick={() => handleCategorySelect(cat)}
                >
                  {cat}
                </span>
              ))}
            </nav>
          </div>
        </div>

        {/* Tier 3: L2 Subcategory Bar (Only shown on Category Listing pages, hidden on Article Detail page) */}
        {!selectedArticle && selectedL1 !== "All" && activeL2Subcategories.length > 0 && (
          <div style={{ background: '#090a0f', borderTop: '1px solid #1e293b', padding: '12px 0' }}>
            <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '0 24px', display: 'flex', gap: '10px', overflowX: 'auto', alignItems: 'center' }}>
              <span style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 'bold', marginRight: '8px', whiteSpace: 'nowrap' }}>
                SUBCATEGORIES:
              </span>
              <button 
                style={{ 
                  background: selectedL2 === 'All' ? '#6366f1' : '#1e293b', 
                  color: '#fff', 
                  border: selectedL2 === 'All' ? 'none' : '1px solid #334155', 
                  padding: '6px 16px', 
                  borderRadius: '20px', 
                  fontSize: '13px', 
                  fontWeight: '600',
                  cursor: 'pointer', 
                  whiteSpace: 'nowrap' 
                }}
                onClick={() => handleSubcategorySelect("All")}
              >
                All {selectedL1} →
              </button>
              {activeL2Subcategories.map(l2Name => (
                <button 
                  key={l2Name} 
                  style={{ 
                    background: selectedL2 === l2Name ? '#6366f1' : '#1e293b', 
                    color: '#fff', 
                    border: selectedL2 === l2Name ? 'none' : '1px solid #334155', 
                    padding: '6px 16px', 
                    borderRadius: '20px', 
                    fontSize: '13px', 
                    fontWeight: '600',
                    cursor: 'pointer', 
                    whiteSpace: 'nowrap' 
                  }}
                  onClick={() => handleSubcategorySelect(l2Name)}
                >
                  {l2Name} →
                </button>
              ))}
            </div>
          </div>
        )}
      </header>

      {/* Main Body Content */}
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
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                      <span style={{ color: '#a3e635', fontSize: '13px', fontWeight: 'bold', textTransform: 'uppercase' }}>
                        {articleDetail.category_name}
                      </span>
                      <span style={{ background: '#f59e0b', color: '#111827', fontWeight: 'bold', padding: '4px 12px', borderRadius: '14px', fontSize: '13px', boxShadow: '0 2px 8px rgba(245, 158, 11, 0.3)' }}>
                        ★ {Number(articleDetail.products?.[0]?.rating || articleDetail.rating || 4.6).toFixed(1)} / 5.0 ProvenPick Score
                      </span>
                    </div>

                    <button
                      onClick={() => setShowSubModal(true)}
                      style={{
                        background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                        color: '#fff',
                        border: 'none',
                        padding: '8px 16px',
                        borderRadius: '20px',
                        fontWeight: 'bold',
                        fontSize: '13px',
                        cursor: 'pointer',
                        boxShadow: '0 4px 12px rgba(99, 102, 241, 0.3)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      🔔 Subscribe to Category Alerts
                    </button>
                  </div>

                  <h1 style={{ fontSize: '36px', color: '#fff', marginTop: '8px', marginBottom: '16px', lineHeight: '1.2' }}>
                    {articleDetail.title}
                  </h1>
                  <p style={{ fontSize: '18px', color: '#cbd5e1', lineHeight: '1.7', marginBottom: '24px' }}>
                    {articleDetail.introduction}
                  </p>

                  <div style={{ background: '#1e293b', padding: '28px', borderRadius: '16px', marginBottom: '32px', border: '1px solid #334155' }}>
                    <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', borderBottom: '1px solid #334155', paddingBottom: '16px' }}>
                      {["guide", "proscons", "specs"].map(tab => (
                        <button
                          key={tab}
                          style={{
                            background: activeTab === tab ? '#6366f1' : 'transparent',
                            color: '#fff',
                            border: 'none',
                            padding: '10px 20px',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            fontWeight: 'bold',
                            fontSize: '14px'
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
                        style={{ color: '#f8fafc', lineHeight: '1.9', fontSize: '16px' }} 
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
                              <div key={i} style={{ background: 'rgba(255, 255, 255, 0.03)', borderLeft: '3px solid #34d399', padding: '12px 16px', borderRadius: '8px', color: '#ecfdf5', fontSize: '14px', lineHeight: '1.6' }}>
                                {typeof p === 'string' ? p : p.text}
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Cons Card */}
                        <div style={{ background: 'rgba(244, 63, 94, 0.05)', border: '1px solid rgba(244, 63, 94, 0.3)', borderRadius: '16px', padding: '24px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
                            <div style={{ background: '#f43f5e', color: '#fff', width: '28px', height: '28px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>✕</div>
                            <h4 style={{ color: '#fb7185', fontSize: '18px', fontWeight: 'bold', margin: 0 }}>CONS</h4>
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            {articleDetail.products[0].cons?.map((c, i) => (
                              <div key={i} style={{ background: 'rgba(255, 255, 255, 0.03)', borderLeft: '3px solid #f43f5e', padding: '12px 16px', borderRadius: '8px', color: '#fff1f2', fontSize: '14px', lineHeight: '1.6' }}>
                                {typeof c === 'string' ? c : c.text}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}

                    {activeTab === 'specs' && articleDetail.products?.[0] && (
                      <div style={{ background: '#0f172a', padding: '24px', borderRadius: '12px' }}>
                        <h4 style={{ color: '#fff', marginBottom: '16px', fontSize: '18px' }}>Technical Specifications</h4>
                        <table style={{ width: '100%', borderCollapse: 'collapse', color: '#cbd5e1' }}>
                          <tbody>
                            {Object.entries(articleDetail.products[0].specs || {}).map(([k, v]) => (
                              <tr key={k} style={{ borderBottom: '1px solid #334155' }}>
                                <td style={{ padding: '12px 0', fontWeight: 'bold', width: '30%', textTransform: 'capitalize' }}>{k.replace(/_/g, ' ')}</td>
                                <td style={{ padding: '12px 0' }}>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>

                {/* Sidebar Card with Affiliate Links & Legal Disclosure */}
                <div>
                  {articleDetail.products?.[0] && (
                    <div style={{ background: '#1e293b', padding: '24px', borderRadius: '16px', border: '1px solid #334155', sticky: 'top', top: '20px' }}>
                      {articleDetail.products[0].image_url && (
                        <img 
                          src={articleDetail.products[0].image_url} 
                          alt={articleDetail.products[0].name}
                          style={{ width: '100%', height: '220px', objectFit: 'cover', borderRadius: '12px', marginBottom: '16px' }}
                        />
                      )}
                      <h3 style={{ fontSize: '20px', color: '#fff', marginBottom: '8px' }}>{articleDetail.products[0].name}</h3>
                      
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                        <div style={{ fontSize: '24px', color: '#a3e635', fontWeight: '900' }}>
                          ₹{articleDetail.products[0].price_inr?.toLocaleString() || 'Check Price'}
                        </div>
                        <span style={{ background: '#f59e0b', color: '#111827', fontWeight: 'bold', padding: '2px 8px', borderRadius: '8px', fontSize: '12px' }}>
                          ★ {Number(articleDetail.products[0].rating || 4.6).toFixed(1)} / 5.0
                        </span>
                      </div>
                      
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '16px' }}>
                        {articleDetail.products[0].affiliate_links && articleDetail.products[0].affiliate_links.length > 0 ? (
                          articleDetail.products[0].affiliate_links.map((link) => (
                            <button
                              key={link.id}
                              onClick={() => handleAffiliateClick(link.id, link.tracked_url)}
                              style={{
                                background: link.platform?.toLowerCase().includes('amazon') ? '#f59e0b' : '#2563eb',
                                color: link.platform?.toLowerCase().includes('amazon') ? '#111827' : '#ffffff',
                                border: 'none',
                                padding: '14px 20px',
                                borderRadius: '10px',
                                fontWeight: 'bold',
                                fontSize: '14px',
                                cursor: 'pointer',
                                width: '100%',
                                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)'
                              }}
                            >
                              Check Price on {link.platform} →
                            </button>
                          ))
                        ) : (
                          <>
                            <button
                              onClick={() => window.open(`https://www.amazon.in/s?k=${encodeURIComponent(articleDetail.products[0].name)}&tag=provenpick-21`, '_blank')}
                              style={{ background: '#f59e0b', color: '#111827', border: 'none', padding: '14px 20px', borderRadius: '10px', fontWeight: 'bold', fontSize: '14px', cursor: 'pointer', width: '100%', boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)' }}
                            >
                              Check Price on Amazon →
                            </button>
                            <button
                              onClick={() => window.open(`https://www.flipkart.com/search?q=${encodeURIComponent(articleDetail.products[0].name)}&affid=provenpick`, '_blank')}
                              style={{ background: '#2563eb', color: '#ffffff', border: 'none', padding: '14px 20px', borderRadius: '10px', fontWeight: 'bold', fontSize: '14px', cursor: 'pointer', width: '100%', boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)' }}
                            >
                              Check Price on Flipkart →
                            </button>
                          </>
                        )}
                      </div>

                      {/* Monetization Disclosure */}
                      <p style={{ fontSize: '11px', color: '#94a3b8', lineHeight: '1.4', margin: 0, textAlign: 'center', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '12px' }}>
                        ⚖️ <strong>Affiliate Disclosure:</strong> Buying through these links earns ProvenPick a small commission at no extra cost to you, supporting our independent product testing.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          /* Homepage Category View */
          <div>
            {/* Featured Carousel Block */}
            {selectedL1 === "All" && currentBestItem && currentBestItem.article && (
              <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '24px', marginBottom: '48px' }}>
                <div style={{ background: '#fef08a', color: '#111827', padding: '32px 24px', borderRadius: '16px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                  <div>
                    <h2 style={{ fontSize: '42px', fontWeight: '900', margin: '0 0 8px 0', letterSpacing: '-1px' }}>BEST</h2>
                    <p style={{ fontSize: '13px', color: '#4b5563', margin: '0 0 24px 0' }}>Top rated picks from each category</p>
                    
                    <div style={{ background: '#111827', color: '#fff', padding: '6px 12px', borderRadius: '6px', display: 'inline-block', fontSize: '11px', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '16px' }}>
                      CATEGORY: {currentBestItem.category}
                    </div>
                    
                    <h3 style={{ fontSize: '16px', fontWeight: 'bold', color: '#111827', lineHeight: '1.4' }}>
                      Best {currentBestItem.category} for 2026: Tested & Reviewed
                    </h3>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '24px' }}>
                    <span style={{ fontSize: '12px', color: '#4b5563', fontWeight: '600' }}>
                      {bestIndex + 1} of {bestCarouselItems.length} Categories
                    </span>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button onClick={() => setBestIndex((prev) => (prev - 1 + bestCarouselItems.length) % bestCarouselItems.length)} style={{ background: '#111827', color: '#fff', border: 'none', width: '32px', height: '32px', borderRadius: '50%', cursor: 'pointer', fontWeight: 'bold' }}>‹</button>
                      <button onClick={() => setBestIndex((prev) => (prev + 1) % bestCarouselItems.length)} style={{ background: '#111827', color: '#fff', border: 'none', width: '32px', height: '32px', borderRadius: '50%', cursor: 'pointer', fontWeight: 'bold' }}>›</button>
                    </div>
                  </div>
                </div>

                {/* Main Hero Card */}
                <div 
                  onClick={() => handleSelectArticle(currentBestItem.article.slug)}
                  style={{ background: '#1e293b', borderRadius: '16px', overflow: 'hidden', cursor: 'pointer', display: 'grid', gridTemplateColumns: '1fr 1fr', border: '1px solid #334155' }}
                >
                  <img 
                    src={currentBestItem.article.mindmap_image_url || currentBestItem.article.products?.[0]?.image_url || 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600'} 
                    alt={currentBestItem.article.title}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                  <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <span style={{ color: '#a3e635', fontSize: '12px', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '8px' }}>
                      FEATURED PICK
                    </span>
                    <h2 style={{ fontSize: '24px', color: '#fff', fontWeight: 'bold', marginBottom: '16px', lineHeight: '1.3' }}>
                      {currentBestItem.article.title}
                    </h2>
                    <p style={{ fontSize: '14px', color: '#cbd5e1', lineHeight: '1.6', marginBottom: '24px' }}>
                      {currentBestItem.article.introduction?.slice(0, 200)}...
                    </p>
                    <span style={{ color: '#a3e635', fontWeight: 'bold', fontSize: '14px' }}>
                      Read Full Review →
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Title Header for Selected Category / Subcategory */}
            <div style={{ marginBottom: '32px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', borderBottom: '1px solid #1e293b', paddingBottom: '16px' }}>
              <div>
                <h2 style={{ fontSize: '28px', color: '#fff', fontWeight: '900', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  {selectedL1 === "All" ? "LATEST HANDS-ON BUYING GUIDES" : `${selectedL1} ${selectedL2 !== 'All' ? `> ${selectedL2}` : ''} (${filteredArticles.length} Guides)`}
                </h2>
                <div style={{ width: '80px', height: '3px', background: '#a3e635', marginTop: '8px' }}></div>
              </div>
            </div>

            {/* Articles Grid */}
            {loading ? (
              <div style={{ padding: '60px 0', textAlign: 'center', color: '#94a3b8' }}>Loading guides...</div>
            ) : filteredArticles.length === 0 ? (
              <div style={{ padding: '60px 0', textAlign: 'center', color: '#94a3b8' }}>
                No guides found under <strong>{selectedL1} {selectedL2 !== 'All' ? `(${selectedL2})` : ''}</strong>. Check back soon!
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '32px' }}>
                {filteredArticles.map(article => (
                  <div 
                    key={article.id}
                    onClick={() => handleSelectArticle(article.slug)}
                    style={{ 
                      background: '#1e293b', 
                      borderRadius: '16px', 
                      overflow: 'hidden', 
                      cursor: 'pointer',
                      border: '1px solid #334155',
                      transition: 'transform 0.2s, box-shadow 0.2s'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.transform = 'translateY(-4px)';
                      e.currentTarget.style.boxShadow = '0 12px 24px rgba(0,0,0,0.4)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'translateY(0)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                  >
                    <img 
                      src={article.mindmap_image_url || article.products?.[0]?.image_url || 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600'} 
                      alt={article.title}
                      loading="lazy"
                      decoding="async"
                      style={{ width: '100%', height: '200px', objectFit: 'cover' }}
                    />
                    <div style={{ padding: '20px' }}>
                      <span style={{ color: '#a3e635', fontSize: '11px', fontWeight: 'bold', textTransform: 'uppercase' }}>
                        {article.category_name}
                      </span>
                      <h3 style={{ fontSize: '18px', color: '#fff', fontWeight: 'bold', marginTop: '6px', marginBottom: '12px', lineHeight: '1.4' }}>
                        {article.title}
                      </h3>
                      <p style={{ fontSize: '13px', color: '#94a3b8', lineHeight: '1.5', marginBottom: '16px' }}>
                        {article.introduction?.slice(0, 110)}...
                      </p>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ color: '#a3e635', fontWeight: 'bold', fontSize: '13px' }}>Read Review →</span>
                        {article.view_count !== undefined && (
                          <span style={{ fontSize: '12px', color: '#64748b' }}>👁 {article.view_count} views</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Subscription Modal Overlay */}
      {showSubModal && (
        <div 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.8)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 99999,
            padding: '24px'
          }}
        >
          <div 
            style={{
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '20px',
              maxWidth: '480px',
              width: '100%',
              padding: '32px',
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.6)',
              position: 'relative'
            }}
          >
            <button 
              onClick={() => { setShowSubModal(false); setSubMsg(null); }}
              style={{ position: 'absolute', top: '16px', right: '16px', background: 'none', border: 'none', color: '#94a3b8', fontSize: '18px', cursor: 'pointer' }}
            >
              ✕
            </button>

            <div style={{ color: '#6366f1', fontSize: '12px', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
              ⚡ KAFKA EVENT ALERTS
            </div>
            <h2 style={{ fontSize: '24px', color: '#fff', fontWeight: 'bold', marginBottom: '8px' }}>
              Subscribe to {articleDetail?.category_name?.split('->')[1] || selectedL1} Reviews
            </h2>
            <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: '1.5', marginBottom: '24px' }}>
              Get instant email notifications whenever a new review is published in <strong>{articleDetail?.category_name || selectedL1}</strong>!
            </p>

            {subMsg ? (
              <div style={{ background: subMsg.startsWith('⚠️') ? 'rgba(239,68,68,0.1)' : 'rgba(52,211,153,0.1)', border: subMsg.startsWith('⚠️') ? '1px solid #ef4444' : '1px solid #34d399', color: subMsg.startsWith('⚠️') ? '#fca5a5' : '#34d399', padding: '16px', borderRadius: '12px', textAlign: 'center', fontWeight: 'bold', fontSize: '14px' }}>
                {subMsg}
              </div>
            ) : (
              <form onSubmit={handleSubscribeSubmit}>
                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '13px', color: '#cbd5e1', marginBottom: '6px', fontWeight: 'bold' }}>Your Full Name:</label>
                  <input 
                    type="text"
                    placeholder="Pradeep Kumar"
                    value={subName}
                    onChange={(e) => setSubName(e.target.value)}
                    required
                    style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '12px 16px', borderRadius: '10px', fontSize: '14px', outline: 'none' }}
                  />
                </div>

                <div style={{ marginBottom: '20px' }}>
                  <label style={{ display: 'block', fontSize: '13px', color: '#cbd5e1', marginBottom: '6px', fontWeight: 'bold' }}>Your Email Address:</label>
                  <input 
                    type="email"
                    placeholder="pradeep@example.com"
                    value={subEmail}
                    onChange={(e) => setSubEmail(e.target.value)}
                    required
                    style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '12px 16px', borderRadius: '10px', fontSize: '14px', outline: 'none' }}
                  />
                </div>

                <div style={{ background: '#0f172a', padding: '12px 16px', borderRadius: '10px', marginBottom: '24px', border: '1px solid #334155' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '13px', color: '#cbd5e1' }}>
                    <input 
                      type="checkbox" 
                      checked={subIncludeL1}
                      onChange={(e) => setSubIncludeL1(e.target.checked)}
                      style={{ accentColor: '#6366f1', width: '16px', height: '16px' }}
                    />
                    Also notify me for ALL reviews under {articleDetail?.category_name?.split('->')[0] || selectedL1}
                  </label>
                </div>

                <button
                  type="submit"
                  disabled={subLoading}
                  style={{ width: '100%', background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', color: '#fff', border: 'none', padding: '14px', borderRadius: '10px', fontWeight: 'bold', fontSize: '15px', cursor: subLoading ? 'wait' : 'pointer' }}
                >
                  {subLoading ? 'Subscribing...' : '🔔 Activate Category Alerts'}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
