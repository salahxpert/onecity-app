package com.onecity.app;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.view.KeyEvent;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ProgressBar;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private ProgressBar progressBar;
    private SwipeRefreshLayout swipeRefreshLayout;
    private static final String APP_URL = "https://onecity-app.onrender.com";
    private static final int CONNECTION_TIMEOUT = 30000; // 30 seconds
    private boolean isLoading = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // Initialize views
        webView = findViewById(R.id.webView);
        progressBar = findViewById(R.id.progressBar);
        swipeRefreshLayout = findViewById(R.id.swipeRefreshLayout);

        // Setup WebView
        setupWebView();

        // Setup Swipe to Refresh
        swipeRefreshLayout.setOnRefreshListener(() -> {
            if (isNetworkAvailable()) {
                webView.reload();
            } else {
                Toast.makeText(MainActivity.this, "No internet connection. Please check your network.", Toast.LENGTH_LONG).show();
                swipeRefreshLayout.setRefreshing(false);
            }
        });

        // Check network and load URL
        if (isNetworkAvailable()) {
            webView.loadUrl(APP_URL);
        } else {
            showNoNetworkPage();
        }
    }

    private void setupWebView() {
        WebSettings webSettings = webView.getSettings();

        // JavaScript
        webSettings.setJavaScriptEnabled(true);

        // Storage
        webSettings.setDomStorageEnabled(true);
        webSettings.setDatabaseEnabled(true);

        // Cache
        webSettings.setCacheMode(WebSettings.LOAD_DEFAULT);

        // Zoom
        webSettings.setSupportZoom(true);
        webSettings.setBuiltInZoomControls(true);
        webSettings.setDisplayZoomControls(false);

        // Layout
        webSettings.setLoadWithOverviewMode(true);
        webSettings.setUseWideViewPort(true);

        // Mixed content (HTTP + HTTPS) for backward compatibility
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            webSettings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        }

        // Form data & password
        webSettings.setSaveFormData(true);
        webSettings.setSavePassword(true);

        // Geolocation
        webSettings.setGeolocationEnabled(true);

        // JavaScript popups
        webSettings.setJavaScriptCanOpenWindowsAutomatically(true);

        // Remote debugging (for developers)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            WebView.setWebContentsDebuggingEnabled(true);
        }

        // ===== COOKIE MANAGEMENT (FIX FOR SESSION ISSUE) =====
        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            cookieManager.setAcceptThirdPartyCookies(webView, true);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            cookieManager.flush();
        } else {
            android.webkit.CookieSyncManager.createInstance(this);
            android.webkit.CookieSyncManager.getInstance().sync();
        }

        // ===== WEB VIEW CLIENT =====
        webView.setWebViewClient(new WebViewClient() {

            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                super.onPageStarted(view, url, favicon);
                isLoading = true;
                progressBar.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                isLoading = false;
                progressBar.setVisibility(View.GONE);
                if (swipeRefreshLayout.isRefreshing()) {
                    swipeRefreshLayout.setRefreshing(false);
                }
                // Sync cookies after page load
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                    CookieManager.getInstance().flush();
                } else {
                    android.webkit.CookieSyncManager.getInstance().sync();
                }
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                super.onReceivedError(view, request, error);
                isLoading = false;
                progressBar.setVisibility(View.GONE);
                if (swipeRefreshLayout.isRefreshing()) {
                    swipeRefreshLayout.setRefreshing(false);
                }
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    if (error.getErrorCode() == ERROR_HOST_LOOKUP || error.getErrorCode() == ERROR_CONNECT) {
                        showNoNetworkPage();
                    }
                } else {
                    // Fallback for older devices
                    if (!isNetworkAvailable()) {
                        showNoNetworkPage();
                    }
                }
                Toast.makeText(MainActivity.this, "Connection error. Please try again.", Toast.LENGTH_LONG).show();
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (url.startsWith(APP_URL) || url.startsWith("https://onecity-app.onrender.com")) {
                    view.loadUrl(url);
                    return true;
                }
                // Allow external links to open in browser (optional)
                // Uncomment the following lines to open external links in browser
                // Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                // startActivity(intent);
                return true;
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                if (url.startsWith(APP_URL) || url.startsWith("https://onecity-app.onrender.com")) {
                    view.loadUrl(url);
                    return true;
                }
                return true;
            }

            @Override
            public void onReceivedSslError(WebView view, android.webkit.SslErrorHandler handler, android.net.http.SslError error) {
                // For production: Cancel and show error message
                handler.cancel();
                Toast.makeText(MainActivity.this, "SSL Error: Secure connection failed.", Toast.LENGTH_LONG).show();
                // For testing only (never use in production):
                // handler.proceed();
            }
        });

        // ===== WEB CHROME CLIENT =====
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                if (newProgress < 100) {
                    progressBar.setVisibility(View.VISIBLE);
                    progressBar.setProgress(newProgress);
                } else {
                    progressBar.setVisibility(View.GONE);
                }
            }

            @Override
            public void onReceivedTitle(WebView view, String title) {
                super.onReceivedTitle(view, title);
                // Optionally update activity title
                // setTitle(title);
            }
        });

        // ===== TIMEOUT HANDLING =====
        webSettings.setLoadsImagesAutomatically(true);
        webSettings.setBlockNetworkLoads(false);

        // Fallback timeout
        new Handler().postDelayed(() -> {
            if (isLoading) {
                progressBar.setVisibility(View.GONE);
                isLoading = false;
                Toast.makeText(MainActivity.this, "Connection timeout. Please check your network.", Toast.LENGTH_SHORT).show();
            }
        }, CONNECTION_TIMEOUT);
    }

    // ===== NETWORK AVAILABILITY CHECK =====
    private boolean isNetworkAvailable() {
        ConnectivityManager connectivityManager = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        NetworkInfo activeNetworkInfo = connectivityManager.getActiveNetworkInfo();
        return activeNetworkInfo != null && activeNetworkInfo.isConnected();
    }

    // ===== SHOW NO NETWORK PAGE =====
    private void showNoNetworkPage() {
        String noNetworkHtml = "<html><head><style>body{font-family:sans-serif;text-align:center;padding:40px;color:#666;}</style></head><body><h2>No Internet Connection</h2><p>Please check your network settings and try again.</p><p><button onclick=\"location.reload()\" style=\"padding:12px 24px;background:#0d6efd;color:white;border:none;border-radius:4px;font-size:16px;\">Retry</button></p></body></html>";
        webView.loadDataWithBaseURL(null, noNetworkHtml, "text/html", "UTF-8", null);
    }

    // ===== BACK BUTTON HANDLING =====
    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    // ===== SAVE INSTANCE STATE =====
    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        webView.saveState(outState);
    }

    @Override
    protected void onRestoreInstanceState(Bundle savedInstanceState) {
        super.onRestoreInstanceState(savedInstanceState);
        webView.restoreState(savedInstanceState);
    }

    // ===== CLEAR COOKIES (LOGOUT) =====
    public void clearCookies() {
        CookieManager.getInstance().removeAllCookies(null);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            CookieManager.getInstance().flush();
        } else {
            android.webkit.CookieSyncManager.getInstance().sync();
        }
    }
}