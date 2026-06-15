# Deploy in Streamlit Cloud

To deploy your Beepov app to Streamlit Cloud, follow these step-by-step instructions:

1. Sign In to Streamlit Cloud
   * Navigate to [share.streamlit.io](https://share.streamlit.io).
   * Click "Continue with GitHub" and sign in using your GitHub account.

2. Create a New App
   * Once logged in, click the "Create app" button in the upper right corner of your workspace.
   * Select "Yup, I have an app" if prompted (since your repository already exists).

3. Configure Your Repository Settings
   Fill in the deployment details exactly as follows:
   * **Repository:** aouirora/beepov
   * **Branch:** feature/cloud-deployment (This is the branch containing your latest updates).
   * **Main file path:** app.py

4. Launch the App
   * Click "Deploy!".
   * Streamlit will now provision a server, read your requirements.txt, install the necessary libraries, and launch your live map. This usually takes 1–3 minutes.

---

### Tips for Managing Your Deployment
* **Custom URL:** Once deployed, you can change the default URL to something more readable (like beepov-berlin.streamlit.app) by clicking Settings > App URL in your Streamlit dashboard.
* **Continuous Deployment:** Any new changes you push to the feature/cloud-deployment branch will trigger an automatic redeploy.
* **Resource Monitoring:** Use the "Manage App" console (the small terminal icon at the bottom right of your live app) to check for errors and monitor RAM usage. Ensure it stays under 1GB to remain within the free tier limits.
