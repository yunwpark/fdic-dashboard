# FDIC 2025 Q4 dashboard for GitHub Pages

GitHub Actions runs Python to fetch the December 31, 2025 FDIC data, validate the accounting identity, and generate an HTML page and two CSV downloads. GitHub Pages serves those files. Chrome displays the HTML and CSS, draws the charts using Chart.js from a CDN, and filters the table in the browser.

## Publish on GitHub Free

1. Create a public GitHub repository, for example `fdic-dashboard`, with `main` as its default branch.
2. Extract the ZIP and commit its contents to the repository root, including the hidden `.github` folder. Verify that `.github/workflows/pages.yml` appears on GitHub. Upload the extracted files, with their folder structure preserved.
3. Open the repository's **Settings → Pages**. Under **Build and deployment**, set **Source** to **GitHub Actions**.
4. Open **Actions → Publish FDIC dashboard → Run workflow**, select `main`, and run it. Open the site URL shown in the successful deployment or under **Settings → Pages**. It normally has the form `https://YOUR-USERNAME.github.io/fdic-dashboard/`.
5. To fetch the FDIC figures again, rerun the workflow. A push to `main` also builds a new snapshot. Reloading the dashboard displays the currently published snapshot.

If the build fails, check the **Actions** log, especially the `python build_site.py` step. A failed fetch or accounting validation prevents that run from deploying.

## Compare with the original Flask package

| Responsibility | Local Flask version | GitHub Pages version |
| --- | --- | --- |
| Fetch and validate FDIC data | Flask calls `fdic_service.py` when fresh results are needed | GitHub Actions runs `build_site.py`, which calls the same `fdic_service.py` |
| Create HTML | Flask fills the Jinja template when Chrome requests the dashboard | Python fills the Jinja template during the build |
| Download CSVs | Flask responds with generated CSV attachments | Pages serves two CSV files written during the build |
| Refresh source data | Dashboard button sends a POST to Flask | Repository maintainer runs the workflow |
| Charts and filter | JavaScript in Chrome | JavaScript in Chrome |

## Optional local preview

With Python 3.12 and the project folder open in your terminal, run:

```powershell
python -m pip install -r requirements.txt
python build_site.py
python -m http.server 8000 --bind 127.0.0.1 --directory _site
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The build needs access to the FDIC API. The charts need access to the Chart.js CDN.
