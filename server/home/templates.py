"""
X87 Player - Home Page Templates
All HTML templates for the landing page
Current Date and Time (UTC): 2025-11-23 10:38:00
Current User: covchump
UPDATED: Removed System Status and Admin Panel links
"""

# Base styles shared across all pages
BASE_STYLES = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background: #0a0a0a;
        color: white;
        overflow-x: hidden;
    }
    .gradient-bg {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        opacity: 0.1;
        z-index: -1;
    }
    .container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 0 20px;
    }
    nav {
        background: rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(10px);
        padding: 1rem 0;
        position: fixed;
        width: 100%;
        top: 0;
        z-index: 1000;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    .nav-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .logo {
        font-size: 1.8rem;
        font-weight: bold;
        color: white;
        text-decoration: none;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .nav-links {
        display: flex;
        gap: 2rem;
        align-items: center;
    }
    .nav-link {
        color: rgba(255, 255, 255, 0.9);
        text-decoration: none;
        transition: color 0.3s;
        font-weight: 500;
    }
    .nav-link:hover {
        color: #667eea;
    }
    .btn {
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 600;
        transition: all 0.3s;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        cursor: pointer;
        border: none;
    }
    .btn-primary {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    .btn-primary:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
    }
    .btn-secondary {
        background: transparent;
        color: white;
        border: 2px solid rgba(255, 255, 255, 0.3);
    }
    .btn-secondary:hover {
        background: rgba(255, 255, 255, 0.1);
        border-color: rgba(255, 255, 255, 0.5);
    }
    .btn-success {
        background: linear-gradient(135deg, #10b981, #34d399);
        color: white;
    }
    .btn-success:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 30px rgba(16, 185, 129, 0.4);
    }
    .btn-gold {
        background: linear-gradient(135deg, #ffd700, #ffed4e);
        color: #1a1a1a;
    }
    .btn-gold:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 30px rgba(255, 215, 0, 0.4);
    }
    .btn-purple {
        background: linear-gradient(135deg, #8b5cf6, #d946ef);
        color: white;
    }
    .btn-purple:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 30px rgba(139, 92, 246, 0.4);
    }
    .status-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }
    .status-online {
        background: #10b981;
        color: white;
    }
    .status-offline {
        background: #ef4444;
        color: white;
    }
    .status-checking {
        background: #f59e0b;
        color: white;
    }
    @media (max-width: 768px) {
        .nav-links {
            display: none;
        }
    }
"""

HOME_PAGE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>X87 Player - Professional IPTV Player for Windows, Android & iOS</title>
    <style>
        ''' + BASE_STYLES + '''
        .hero {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 100px 20px 50px;
            position: relative;
        }
        .hero-content {
            text-align: center;
            max-width: 1200px;
            width: 100%;
            animation: fadeInUp 1s ease;
        }
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        .hero-icon {
            font-size: 5rem;
            margin-bottom: 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
        h1 {
            font-size: 4rem;
            margin-bottom: 1.5rem;
            background: linear-gradient(135deg, #ffffff 0%, #e0e0e0 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .tagline {
            font-size: 1.5rem;
            color: rgba(255, 255, 255, 0.8);
            margin-bottom: 3rem;
            line-height: 1.6;
        }
        .tagline small {
            display: block;
            margin-top: 1rem;
            font-size: 1rem;
            color: rgba(255, 255, 255, 0.5);
        }
        
        /* Plans section */
        .plans-section {
            margin: 4rem 0;
            padding: 2rem;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 20px;
        }
        .plans-header {
            text-align: center;
            margin-bottom: 3rem;
        }
        .plans-header h2 {
            font-size: 2.5rem;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #ffffff 0%, #e0e0e0 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .plans-header p {
            color: rgba(255, 255, 255, 0.8);
            font-size: 1.2rem;
        }
        
        /* 3-column horizontal layout */
        .plans-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 2rem;
            margin-bottom: 2rem;
        }
        
        @media (min-width: 1024px) {
            .plans-grid {
                grid-template-columns: repeat(3, 1fr);
            }
        }
        
        .plan-card {
            background: rgba(255, 255, 255, 0.05);
            border: 2px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 2.5rem;
            text-align: center;
            transition: all 0.3s;
            position: relative;
            backdrop-filter: blur(10px);
            display: flex;
            flex-direction: column;
        }
        .plan-card:hover {
            transform: translateY(-10px);
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(102, 126, 234, 0.5);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
        }
        .plan-card.featured {
            border-color: #ffd700;
            transform: scale(1.05);
            background: rgba(255, 215, 0, 0.05);
            z-index: 10;
        }
        .plan-card.featured:hover {
            transform: scale(1.05) translateY(-10px);
        }
        .plan-badge {
            position: absolute;
            top: -15px;
            left: 50%;
            transform: translateX(-50%);
            background: linear-gradient(135deg, #ffd700, #ffed4e);
            color: #1a1a1a;
            padding: 0.5rem 1.5rem;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.875rem;
            white-space: nowrap;
        }
        .plan-icon {
            font-size: 4rem;
            margin-bottom: 1.5rem;
        }
        .plan-title {
            font-size: 2rem;
            color: white;
            margin-bottom: 0.5rem;
        }
        .plan-price {
            font-size: 3rem;
            font-weight: bold;
            margin: 1rem 0;
        }
        .plan-price.free {
            background: linear-gradient(135deg, #10b981, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .plan-price.lifetime {
            background: linear-gradient(135deg, #ffd700, #ffed4e);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .plan-price.business {
            background: linear-gradient(135deg, #8b5cf6, #d946ef);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .plan-price small {
            font-size: 1rem;
            color: rgba(255, 255, 255, 0.7);
            font-weight: normal;
        }
        .plan-duration {
            color: rgba(255, 255, 255, 0.7);
            margin-bottom: 2rem;
            font-size: 1.125rem;
        }
        .plan-features {
            list-style: none;
            margin-bottom: 2rem;
            text-align: left;
            flex-grow: 1;
        }
        .plan-features li {
            padding: 0.75rem 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            align-items: center;
            gap: 0.75rem;
            color: rgba(255, 255, 255, 0.9);
        }
        .plan-features li:last-child {
            border-bottom: none;
        }
        .feature-icon {
            color: #10b981;
            font-size: 1.25rem;
        }
        .plan-btn {
            width: 100%;
            padding: 1rem;
            font-size: 1.125rem;
            border-radius: 10px;
            font-weight: 600;
            text-align: center;
            display: inline-block;
            text-decoration: none;
            transition: all 0.3s;
            margin-top: auto;
        }
        
        .hero-buttons {
            display: flex;
            gap: 1.5rem;
            justify-content: center;
            flex-wrap: wrap;
            margin-bottom: 3rem;
        }
        .features-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 2rem;
            margin: 4rem 0;
        }
        .feature-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 2rem;
            text-align: center;
            transition: all 0.3s;
            backdrop-filter: blur(10px);
        }
        .feature-card:hover {
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(102, 126, 234, 0.5);
        }
        .feature-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
            display: block;
        }
        .feature-title {
            font-size: 1.3rem;
            margin-bottom: 1rem;
            color: white;
        }
        .feature-desc {
            color: rgba(255, 255, 255, 0.7);
            line-height: 1.6;
        }
        .stats-section {
            padding: 4rem 0;
            background: rgba(0, 0, 0, 0.3);
            margin: 4rem 0;
            border-radius: 20px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 2rem;
            text-align: center;
        }
        .stat-item {
            padding: 1rem;
        }
        .stat-number {
            font-size: 3rem;
            font-weight: bold;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stat-label {
            color: rgba(255, 255, 255, 0.7);
            margin-top: 0.5rem;
        }
        footer {
            padding: 3rem 0;
            text-align: center;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            margin-top: 4rem;
        }
        .footer-links {
            display: flex;
            gap: 2rem;
            justify-content: center;
            margin-top: 1rem;
        }
        .footer-link {
            color: rgba(255, 255, 255, 0.6);
            text-decoration: none;
            transition: color 0.3s;
        }
        .footer-link:hover {
            color: white;
        }
        @media (max-width: 1023px) {
            .plan-card.featured { transform: scale(1); }
            .plan-card.featured:hover { transform: translateY(-10px); }
        }
        @media (max-width: 768px) {
            h1 { font-size: 2.5rem; }
            .hero-icon { font-size: 3rem; }
            .tagline { font-size: 1.2rem; }
            .hero-buttons { flex-direction: column; align-items: center; }
            .btn { width: 100%; max-width: 300px; justify-content: center; }
        }
    </style>
</head>
<body>
    <div class="gradient-bg"></div>
    
    <nav>
        <div class="container">
            <div class="nav-content">
                <a href="/" class="logo">
                    <span>🎬</span>
                    <span>X87 Player</span>
                </a>
                <div class="nav-links">
                    <a href="/features" class="nav-link">Features</a>
                    <a href="/pricing" class="nav-link">Pricing</a>
                    <a href="/portal" class="btn btn-primary">
                        <span>👤</span>
                        <span>Customer Portal</span>
                    </a>
                </div>
            </div>
        </div>
    </nav>
    
    <section class="hero">
        <div class="hero-content">
            <div class="hero-icon">🎬</div>
            <h1>X87 Player</h1>
            <p class="tagline">
                The Professional Xtream Codes Player — Available on Windows, Android &amp; iOS<br>
                A powerful player for your Xtream Codes service — no streams provided, just the best way to watch them.
                <small>(Server URL, Username &amp; Password required to connect)</small>
            </p>
            
            <!-- Plans Section -->
            <div class="plans-section">
                <div class="plans-header">
                    <h2>Choose Your Plan</h2>
                    <p>Simple pricing for everyone</p>
                </div>
                
                <div class="plans-grid">
                    <!-- Free Trial Card -->
                    <div class="plan-card">
                        <div class="plan-icon">🎁</div>
                        <h3 class="plan-title">Free Trial</h3>
                        <div class="plan-price free">FREE</div>
                        <div class="plan-duration">7 days · up to 3 devices</div>
                        
                        <ul class="plan-features">
                            <li>
                                <span class="feature-icon">✅</span>
                                <span>Full access to platform</span>
                            </li>
                            <li>
                                <span class="feature-icon">✅</span>
                                <span>Windows, Android &amp; iOS</span>
                            </li>
                            <li>
                                <span class="feature-icon">✅</span>
                                <span>No credit card required</span>
                            </li>
                        </ul>
                        
                        <a href="/register-trial" class="plan-btn btn-success">
                            <span>🚀 Start Free Trial</span>
                        </a>
                    </div>
                    
                    <!-- Lifetime Plan Card -->
                    <div class="plan-card featured">
                        <div class="plan-badge">BEST VALUE</div>
                        <div class="plan-icon">⭐</div>
                        <h3 class="plan-title">Yearly</h3>
                        <div class="plan-price lifetime">
                            £4.99
                            <small>/year</small>
                        </div>
                        <div class="plan-duration">Single Licence - Up to 5 devices</div>
                        
                        <ul class="plan-features">
                            <li>
                                <span class="feature-icon">✅</span>
                                <span>Windows, Android &amp; iOS</span>
                            </li>
                            <li>
                                <span class="feature-icon">✅</span>
                                <span>Free Updates Included</span>
                            </li>
                            <li>
                                <span class="feature-icon">✅</span>
                                <span>Priority Support</span>
                            </li>
                            <li>
                                <span class="feature-icon">✅</span>
                                <span>No Hidden Fees</span>
                            </li>
                        </ul>
                        
                        <a href="/purchase" class="plan-btn btn-gold">
                            <span>💳 Subscribe Yearly</span>
                        </a>
                    </div>

                    <!-- Rebranding Plan Card -->
                    <div class="plan-card">
                        <div class="plan-icon">🏢</div>
                        <h3 class="plan-title">Rebrand</h3>
                        <div class="plan-price business">
                            £9.99
                            <small>/month</small>
                        </div>
                        <div class="plan-duration">Unlimited devices</div>
                        
                        <ul class="plan-features">
                            <li>
                                <span class="feature-icon">✅</span>
                                <span>Custom App Branding</span>
                            </li>
                            <li>
                                <span class="feature-icon">✅</span>
                                <span>Unlimited Devices</span>
                            </li>
                            <li>
                                <span class="feature-icon">✅</span>
                                <span>Your Logo &amp; Name</span>
                            </li>
                            <li>
                                <span class="feature-icon">✅</span>
                                <span>Hidden DNS</span>
                            </li>
                        </ul>
                        
                        <a href="/purchase" class="plan-btn btn-purple">
                            <span>💼 Get Branded</span>
                        </a>
                    </div>
                </div>
            </div>
            
            <div class="hero-buttons">
                <a href="/portal" class="btn btn-primary" style="font-size: 1.1rem; padding: 1rem 2rem;">
                    <span>🎯</span>
                    <span>Customer Portal</span>
                </a>
            </div>
        </div>
    </section>
    
    <section class="container">
        <div class="features-grid">
            <div class="feature-card">
                <span class="feature-icon">📺</span>
                <h3 class="feature-title">Live TV</h3>
                <p class="feature-desc">Stream thousands of live channels instantly via Xtream Codes</p>
            </div>
            <div class="feature-card">
                <span class="feature-icon">🎬</span>
                <h3 class="feature-title">Movies &amp; Series</h3>
                <p class="feature-desc">Browse a rich VOD library with artwork, descriptions &amp; categories</p>
            </div>
            <div class="feature-card">
                <span class="feature-icon">🔐</span>
                <h3 class="feature-title">Secure &amp; Private</h3>
                <p class="feature-desc">Hardware-bound licensing keeps your credentials and data safe</p>
            </div>
            <div class="feature-card">
                <span class="feature-icon">🎨</span>
                <h3 class="feature-title">Sleek Interface</h3>
                <p class="feature-desc">A modern, dark-themed UI built for effortless navigation</p>
            </div>
            <div class="feature-card">
                <span class="feature-icon">📱</span>
                <h3 class="feature-title">Multi-Platform</h3>
                <p class="feature-desc">Available on Windows, Android &amp; iOS — one account, every device</p>
            </div>
        </div>
        
        <div class="stats-section">
            <div class="container">
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-number">3</div>
                        <div class="stat-label">Platforms</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">24/7</div>
                        <div class="stat-label">Streaming</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">Xtream</div>
                        <div class="stat-label">Compatible</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">Instant</div>
                        <div class="stat-label">Setup</div>
                    </div>
                </div>
            </div>
        </div>
    </section>
    
    <footer>
        <div class="container">
            <p>&copy; 2025 X87 Player. All rights reserved.</p>
            <p style="color: rgba(255,255,255,0.6); margin-top: 0.5rem;">Developed by covchump</p>
            <div class="footer-links">
                <a href="/features" class="footer-link">Features</a>
                <a href="/pricing" class="footer-link">Pricing</a>
                <a href="/portal" class="footer-link">Portal</a>
                <a href="/register-trial" class="footer-link">Free Trial</a>
            </div>
        </div>
    </footer>
</body>
</html>
'''

FEATURES_PAGE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Features - X87 Player</title>
    <style>
        ''' + BASE_STYLES + '''
        .page-header {
            padding: 150px 0 50px;
            text-align: center;
            background: linear-gradient(180deg, rgba(102,126,234,0.1) 0%, transparent 100%);
        }
        h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        .features-section {
            padding: 4rem 0;
        }
        .feature-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 4rem;
            align-items: center;
            margin-bottom: 6rem;
        }
        .feature-row:nth-child(even) {
            direction: rtl;
        }
        .feature-row:nth-child(even) > * {
            direction: ltr;
        }
        .feature-content h2 {
            font-size: 2rem;
            margin-bottom: 1rem;
            color: white;
        }
        .feature-content p {
            color: rgba(255,255,255,0.8);
            line-height: 1.8;
            margin-bottom: 1.5rem;
        }
        .feature-list {
            list-style: none;
        }
        .feature-list li {
            padding: 0.5rem 0;
            color: rgba(255,255,255,0.9);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .feature-image {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 20px;
            padding: 3rem;
            text-align: center;
            font-size: 8rem;
        }
        @media (max-width: 768px) {
            .feature-row {
                grid-template-columns: 1fr;
            }
            .feature-row:nth-child(even) {
                direction: ltr;
            }
        }
    </style>
</head>
<body>
    <div class="gradient-bg"></div>
    
    <nav>
        <div class="container">
            <div class="nav-content">
                <a href="/" class="logo">
                    <span>🎬</span>
                    <span>X87 Player</span>
                </a>
                <div class="nav-links">
                    <a href="/" class="nav-link">Home</a>
                    <a href="/features" class="nav-link">Features</a>
                    <a href="/pricing" class="nav-link">Pricing</a>
                    <a href="/portal" class="btn btn-primary">Customer Portal</a>
                </div>
            </div>
        </div>
    </nav>
    
    <div class="page-header">
        <div class="container">
            <h1>Powerful Features</h1>
            <p style="font-size: 1.3rem; color: rgba(255,255,255,0.8);">The professional Xtream Codes player for Windows, Android &amp; iOS</p>
        </div>
    </div>
    
    <section class="features-section">
        <div class="container">
            <div class="feature-row">
                <div class="feature-content">
                    <h2>Xtream Codes Compatible</h2>
                    <p>Connect easily using your existing Xtream Codes credentials. Just enter your username, password, and server URL.</p>
                    <ul class="feature-list">
                        <li><span>✅</span> Instant connection</li>
                        <li><span>✅</span> Secure login</li>
                        <li><span>✅</span> Playlist management</li>
                        <li><span>✅</span> Auto-update</li>
                    </ul>
                </div>
                <div class="feature-image">📺</div>
            </div>
            
            <div class="feature-row">
                <div class="feature-content">
                    <h2>Windows Native & VLC Powered</h2>
                    <p>Built specifically for Windows and powered by the ultra-reliable VLC media engine for maximum performance.</p>
                    <ul class="feature-list">
                        <li><span>✅</span> VLC Playback Engine</li>
                        <li><span>✅</span> Hardware acceleration</li>
                        <li><span>✅</span> Multi-monitor support</li>
                        <li><span>✅</span> Smooth 4K playback</li>
                    </ul>
                </div>
                <div class="feature-image">🟠</div>
            </div>
            
            <div class="feature-row">
                <div class="feature-content">
                    <h2>Secure Platform</h2>
                    <p>Your credentials and viewing data are kept secure with our advanced player technology.</p>
                    <ul class="feature-list">
                        <li><span>✅</span> Hardware binding</li>
                        <li><span>✅</span> Encrypted storage</li>
                        <li><span>✅</span> Privacy focused</li>
                        <li><span>✅</span> No data sharing</li>
                    </ul>
                </div>
                <div class="feature-image">🔐</div>
            </div>
        </div>
    </section>
    
    <footer>
        <div class="container">
            <p>&copy; 2025 X87 Player. All rights reserved.</p>
        </div>
    </footer>
</body>
</html>
'''

PRICING_PAGE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pricing - X87 Player</title>
    <style>
        ''' + BASE_STYLES + '''
        .page-header {
            padding: 150px 0 50px;
            text-align: center;
        }
        h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        .pricing-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 2rem;
            margin: 4rem 0;
        }
        @media (min-width: 1024px) {
            .pricing-grid {
                grid-template-columns: repeat(3, 1fr);
            }
        }
        .pricing-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 20px;
            padding: 2rem;
            text-align: center;
            position: relative;
            transition: transform 0.3s;
            display: flex;
            flex-direction: column;
        }
        .pricing-card.featured {
            border-color: #ffd700;
            transform: scale(1.05);
            background: rgba(255, 215, 0, 0.05);
            z-index: 10;
        }
        .pricing-card:hover {
            transform: translateY(-10px);
        }
        .pricing-card.featured:hover {
            transform: scale(1.05) translateY(-10px);
        }
        .plan-name {
            font-size: 1.5rem;
            margin-bottom: 1rem;
            color: white;
        }
        .plan-price {
            font-size: 3rem;
            font-weight: bold;
            margin: 1rem 0;
        }
        .plan-price.free {
            background: linear-gradient(135deg, #10b981, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .plan-price.lifetime {
            background: linear-gradient(135deg, #ffd700, #ffed4e);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .plan-price.business {
            background: linear-gradient(135deg, #8b5cf6, #d946ef);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .plan-period {
            color: rgba(255,255,255,0.6);
            margin-bottom: 2rem;
        }
        .plan-features {
            list-style: none;
            margin: 2rem 0;
            text-align: left;
            flex-grow: 1;
        }
        .plan-features li {
            padding: 0.75rem 0;
            color: rgba(255,255,255,0.9);
            border-bottom: 1px solid rgba(255,255,255,0.05);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .plan-features li:last-child {
            border-bottom: none;
        }
        .popular-badge {
            position: absolute;
            top: -15px;
            right: 50%;
            transform: translateX(50%);
            background: linear-gradient(135deg, #ffd700, #ffed4e);
            color: #1a1a1a;
            padding: 5px 20px;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: 600;
            white-space: nowrap;
        }
        .pricing-btn {
            width: 100%;
            margin-top: auto;
        }
        @media (max-width: 1023px) {
            .pricing-card.featured { transform: scale(1); }
            .pricing-card.featured:hover { transform: translateY(-10px); }
        }
    </style>
</head>
<body>
    <div class="gradient-bg"></div>
    
    <nav>
        <div class="container">
            <div class="nav-content">
                <a href="/" class="logo">
                    <span>🎬</span>
                    <span>X87 Player</span>
                </a>
                <div class="nav-links">
                    <a href="/" class="nav-link">Home</a>
                    <a href="/features" class="nav-link">Features</a>
                    <a href="/pricing" class="nav-link">Pricing</a>
                    <a href="/register-trial" class="btn btn-primary">Get Started</a>
                </div>
            </div>
        </div>
    </nav>
    
    <div class="page-header">
        <div class="container">
            <h1>Simple, Transparent Pricing</h1>
            <p style="font-size: 1.3rem; color: rgba(255,255,255,0.8);">License the player for your personal use</p>
        </div>
    </div>
    
    <section class="container">
        <div class="pricing-grid">
            <div class="pricing-card">
                <h3 class="plan-name">Free Trial</h3>
                <div class="plan-price free">FREE</div>
                <div class="plan-period">7 days · up to 3 devices</div>
                <ul class="plan-features">
                    <li><span>✅</span> Full player access</li>
                    <li><span>✅</span> Windows, Android &amp; iOS</li>
                    <li><span>✅</span> No credit card</li>
                </ul>
                <a href="/register-trial" class="btn btn-secondary pricing-btn">Start Trial</a>
            </div>
            
            <div class="pricing-card featured">
                <span class="popular-badge">Best Value</span>
                <h3 class="plan-name">Yearly</h3>
                <div class="plan-price lifetime">£4.99</div>
                <div class="plan-period">per year</div>
                <ul class="plan-features">
                    <li><span>✅</span> Windows, Android &amp; iOS</li>
                    <li><span>✅</span> Free Updates Included</li>
                    <li><span>✅</span> Priority Support</li>
                    <li><span>✅</span> No Hidden Fees</li>
                </ul>
                <a href="/purchase" class="btn btn-gold pricing-btn">Subscribe Yearly</a>
            </div>
            
            <div class="pricing-card">
                <h3 class="plan-name">Rebrand</h3>
                <div class="plan-price business">£9.99</div>
                <div class="plan-period">per month</div>
                <ul class="plan-features">
                    <li><span>✅</span> Custom App Branding</li>
                    <li><span>✅</span> Unlimited Devices</li>
                    <li><span>✅</span> Your Logo &amp; Name</li>
                    <li><span>✅</span> Hidden DNS</li>
                </ul>
                <a href="/purchase" class="btn btn-purple pricing-btn">Contact Sales</a>
            </div>
        </div>
    </section>
    
    <footer>
        <div class="container">
            <p>&copy; 2025 X87 Player. All rights reserved.</p>
        </div>
    </footer>
</body>
</html>
'''