# Deployment Outline: Django/MongoDB & Next.js Campaign Platform

This document provides a conceptual outline for deploying the campaign management platform, which consists of a Django backend (using Pymongo for MongoDB and Celery for task queuing) and a Next.js frontend.

## I. Core Components & Hosting Choices

1.  **Django Backend (API):**
    *   **Hosting:**
        *   **PaaS (Platform as a Service):** Heroku (with custom buildpacks if needed for Pymongo/Celery), Google App Engine, AWS Elastic Beanstalk. Simplifies deployment but might offer less control.
        *   **IaaS (Infrastructure as a Service):** VMs on AWS EC2, Google Compute Engine, Azure VMs, DigitalOcean Droplets. More control, more setup.
        *   **Containers:** Dockerizing the Django app and deploying to Kubernetes (EKS, GKE, AKS) or a container service (AWS ECS, Google Cloud Run). Recommended for scalability and consistency.
    *   **Application Server:** Gunicorn (common for Django) or Uvicorn (if ASGI features are heavily used, though Gunicorn can manage Uvicorn workers).
    *   **Process Management:** Supervisor, systemd, or container orchestrator's process management.

2.  **Next.js Frontend:**
    *   **Hosting Options:**
        *   **Vercel:** Optimized for Next.js, provides SSR, ISR, SSG, Edge Functions seamlessly. Recommended for Next.js.
        *   **Netlify:** Similar to Vercel, good support for Jamstack sites.
        *   **AWS:** S3 (for static export) + CloudFront (CDN), or Amplify, or ECS/EC2 with Node.js server for SSR.
        *   **Google Cloud:** Cloud Storage + CDN, or App Engine, Cloud Run with Node.js server.
        *   **Self-hosted Node.js server:** On a VM or container if SSR/ISR is needed and not using a platform like Vercel.
    *   **Build Process:** `next build` generates an optimized production build. `next start` runs the Node.js server if needed.

3.  **MongoDB Database:**
    *   **Managed Service (Recommended):**
        *   **MongoDB Atlas:** Official DBaaS, handles scaling, backups, monitoring.
        *   Cloud provider specific: AWS DocumentDB (MongoDB compatible), Azure Cosmos DB (with MongoDB API).
    *   **Self-hosted:** On VMs or Kubernetes. Requires significant operational overhead for setup, maintenance, backups, scaling, and security.

4.  **Celery Workers & Broker:**
    *   **Broker (Message Queue):**
        *   **Redis:** Common, good performance. Managed services available (AWS ElastiCache, Google Memorystore, Azure Cache for Redis).
        *   **RabbitMQ:** More robust, feature-rich. Managed services or self-hosted.
    *   **Celery Workers:**
        *   Run as separate processes from the Django app server.
        *   Hosted on VMs or containers, alongside the Django app or on dedicated instances.
        *   Scale horizontally by running more worker processes/nodes.
        *   Process Management: Supervisor, systemd, or container orchestrator.
    *   **Flower (Optional Monitoring):** A web-based tool for monitoring Celery tasks and workers.

5.  **Web Server / Reverse Proxy (e.g., Nginx, Traefik, Caddy):**
    *   **Responsibilities:**
        *   Terminate SSL/TLS.
        *   Serve static files (Django admin static, potentially Next.js static assets if not using a dedicated CDN solution).
        *   Load balance requests to multiple Django application server instances.
        *   Route API requests (e.g., `/api/*`) to the Django backend.
        *   Route frontend requests to the Next.js server/static assets (if co-located or not using a platform like Vercel).
        *   Implement rate limiting, security headers.

6.  **Email Sending Provider (ESP):**
    *   Essential for high-volume sending (1M+ messages in minutes).
    *   Examples: AWS SES, SendGrid, Mailgun, Postmark.
    *   Requires proper setup: domain verification (SPF, DKIM, DMARC), IP warming (if using dedicated IPs), adherence to sending limits and best practices. Configuration will be in Django's settings for Celery tasks to use.

## II. Deployment Strategy & Process

1.  **Infrastructure Provisioning:**
    *   Set up chosen hosting platforms, databases, message brokers.
    *   Configure networking (VPCs, subnets, firewalls, load balancers).
    *   Set up DNS records.

2.  **Containerization (Recommended):**
    *   **Django App Dockerfile:** Include Python, Pymongo, Celery, application code, Gunicorn.
    *   **Next.js App Dockerfile:** (If not using Vercel/Netlify) Include Node.js, dependencies, build artifacts.
    *   **Celery Worker Dockerfile:** Similar to Django app, but with Celery worker command as entry point.
    *   Use Docker Compose for local development and potentially for simpler multi-container deployments.
    *   Use Kubernetes or similar for production orchestration.

3.  **Configuration Management:**
    *   **Environment Variables:** For all sensitive data (database URIs, API keys, secret keys, ESP credentials, Celery broker URL).
        *   Django: `settings.py` reads from environment.
        *   Next.js: `.env.local`, `.env.production` (for `NEXT_PUBLIC_` variables accessible by browser, and server-side only variables).
        *   Celery: Reads from Django settings or environment.
    *   Configuration files for Nginx, Supervisor, etc.

4.  **CI/CD Pipeline (e.g., GitHub Actions, GitLab CI, Jenkins):**
    *   **Build:** Build Docker images, Next.js static assets.
    *   **Test:** Run automated tests (Django tests, Next.js tests).
    *   **Push:** Push Docker images to a container registry (Docker Hub, ECR, GCR, ACR).
    *   **Deploy:**
        *   Django API: Deploy new image to VMs/containers, run database schema setup/migrations for Django's internal tables (if any).
        *   Celery Workers: Deploy new image, restart workers.
        *   Next.js Frontend: Deploy to Vercel/Netlify, or deploy new build/image to chosen hosting.
        *   **Zero-Downtime Deployments:** Use blue/green deployments or rolling updates for Django API and Celery workers.

5.  **Static and Media Files (Django):**
    *   Django's `collectstatic` for admin files.
    *   Serve via Nginx or a CDN (e.g., AWS S3 + CloudFront).
    *   User-uploaded media (if any, for `media_assets` collection) would likely go to a cloud storage solution like S3.

## III. High-Performance Considerations (1M+ messages/min)

*   **MongoDB Scalability:**
    *   Use a managed service like MongoDB Atlas that allows for easy scaling (sharding, replica sets).
    *   Proper indexing is critical (already covered in schema design).
    *   Monitor query performance.
*   **Celery & Broker Scalability:**
    *   Horizontally scale Celery workers significantly.
    *   Use multiple queues for different task priorities if needed (e.g., high-priority for immediate sends, lower for batch processing or stats aggregation).
    *   Ensure Redis/RabbitMQ cluster is appropriately sized and configured for high throughput.
*   **ESP Throughput:**
    *   Work with ESP to ensure your account has the required sending limits.
    *   IP warming is crucial.
*   **Asynchronous Everything:** Ensure all parts of the sending pipeline are non-blocking.
*   **Database Connection Pooling:** Pymongo manages a connection pool. Ensure it's configured appropriately for the number of Celery workers and Django app instances.
*   **Batching in Tasks:**
    *   `process_campaign_sending_task` should efficiently query and batch subscriber IDs.
    *   `send_email_batch_task` should process its batch and interact with the ESP efficiently (many ESPs support batch sending APIs).
    *   Batch database updates for stats.
*   **Load Balancing:** For Django API servers.
*   **Caching:** Use Redis or Memcached for frequently accessed data that doesn't change often (e.g., resolved templates, certain configurations).
*   **Monitoring & Alerting:**
    *   Application Performance Monitoring (APM) for Django and Next.js.
    *   MongoDB monitoring (Atlas provides this, or use tools like Percona PMM).
    *   Celery monitoring (Flower, or broker-specific tools).
    *   ESP delivery rates, bounce rates, complaint rates.
    *   Set up alerts for critical failures or performance degradation.

## IV. Post-Deployment

*   **Data Migration:** Execute the `data_migration_mongo.py` script carefully, ideally in a staging environment first.
*   **Smoke Testing:** Verify all critical functionalities.
*   **Performance Testing:** Specifically for the campaign sending pipeline to ensure it meets the high-volume requirements.
*   **Ongoing Monitoring and Optimization.**
```
