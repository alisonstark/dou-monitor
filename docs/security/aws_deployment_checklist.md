# 🚀 AWS Deployment Security Checklist

## ⚠️ CRITICAL - Must Complete Before Deploy

### 1. Environment Variables
- [ ] `FLASK_SECRET_KEY` gerado com `secrets.token_urlsafe(32)`
- [ ] `ADMIN_PASS_HASH` gerado com `generate_password_hash()`
- [ ] `FLASK_ENV=production` configurado
- [ ] `.env` file exists and is NOT in version control

### 2. Authentication
- [ ] Default admin/admin password changed
- [ ] Strong password (min 12 chars, mixed case, numbers, symbols)
- [ ] Login endpoint `/login` accessible
- [ ] All routes protected with `@login_required`

### 3. CSRF Protection
- [ ] Flask-WTF installed and configured
- [ ] All POST forms include `{{ csrf_token() }}`
- [ ] CSRF tokens validated on submission

### 4. Path Traversal
- [ ] `serve_edital()` validates filenames
- [ ] File paths resolved and checked against base directory
- [ ] Only PDF files allowed for download

### 5. SSRF Protection
- [ ] Webhook URLs validated (HTTPS only)
- [ ] Private IPs blocked (10.x, 192.168.x, 127.x, 169.254.x)
- [ ] Hostname resolution check before HTTP requests

### 6. Security Headers
- [ ] `X-Content-Type-Options: nosniff`
- [ ] `X-Frame-Options: DENY`
- [ ] `X-XSS-Protection: 1; mode=block`
- [ ] `Referrer-Policy: strict-origin-when-cross-origin`
- [ ] HSTS enabled in production (via Nginx/ALB)

### 7. Dependency Security
- [ ] All packages pinned to specific versions
- [ ] `pip-audit` run with no vulnerabilities
- [ ] `safety check` passed
- [ ] `bandit -r src/` passed

## 🔒 AWS Infrastructure Security

### EC2 Instance
- [ ] Security Group allows ONLY 443 (HTTPS) and 22 (SSH)
- [ ] SSH key-pair created and secured
- [ ] IAM instance role with minimal permissions
- [ ] CloudWatch agent installed for logging
- [ ] Automatic security updates enabled
- [ ] Fail2Ban configured for SSH protection

### Application Load Balancer (Recommended)
- [ ] ALB with ACM SSL certificate
- [ ] HTTP to HTTPS redirect configured
- [ ] Target group health checks enabled
- [ ] Access logs to S3 configured
- [ ] WAF (Web Application Firewall) attached

### Network Configuration
- [ ] VPC with public/private subnets
- [ ] Application in private subnet (if using ALB)
- [ ] NAT Gateway for outbound traffic
- [ ] VPC Flow Logs enabled
- [ ] Network ACLs configured

### Storage Security
- [ ] EBS volumes encrypted
- [ ] Automated snapshots configured
- [ ] S3 bucket for backups (if applicable) with encryption
- [ ] S3 bucket policy restricts public access

### Secrets Management
- [ ] Secrets in AWS Secrets Manager OR SSM Parameter Store
- [ ] NO hardcoded secrets in code
- [ ] `.env` file secured with restrictive permissions (600)
- [ ] IAM role permission to read secrets

### Monitoring & Alerting
- [ ] CloudWatch Logs for application logs
- [ ] CloudWatch Alarms:
  - CPU > 80%
  - Memory > 80%
  - Disk > 80%
  - Login failures > 5 in 5 minutes
- [ ] SNS topic for security alerts
- [ ] AWS GuardDuty enabled (threat detection)

## 📝 Pre-Deploy Commands

```bash
# 1. Audit dependencies
pip-audit
safety check

# 2. Static analysis
bandit -r src/

# 3. Check for secrets in code
grep -r "password\|secret\|token" src/ --exclude-dir=__pycache__

# 4. Verify .env not in repo
git ls-files | grep -E "\.env$|\.key$"  # Should return empty

# 5. Test authentication
curl -I https://your-domain.com/  # Should redirect to /login

# 6. Test CSRF
curl -X POST https://your-domain.com/settings/filters  # Should fail with 400
```

## 🧪 Security Testing (Post-Deploy)

### 1. Authentication Bypass
```bash
# Try accessing protected routes without login
curl -I https://your-domain.com/api/concursos  
# Expected: 302 redirect to /login
```

### 2. Path Traversal
```bash
# Try to access files outside editais/
curl https://your-domain.com/editais/..%2F..%2Fdata%2Fdashboard_config.json
# Expected: 400 Bad Request
```

### 3. SSRF Attack
```bash
# Try to set webhook to internal AWS metadata
curl -X POST https://your-domain.com/settings/notifications \
  -d "webhook_url=http://169.254.169.254/latest/meta-data/" \
  -H "Cookie: session=..."
# Expected: 400 Bad Request - Private IP blocked
```

### 4. CSRF Attack
```bash
# Try POST without CSRF token
curl -X POST https://your-domain.com/run/manual \
  -d "days=7" \
  -H "Cookie: session=..."
# Expected: 400 Bad Request - CSRF token missing
```

### 5. XSS Attack
```bash
# Try injecting JavaScript in search
curl "https://your-domain.com/?q=<script>alert('XSS')</script>"
# Expected: Script tags escaped in HTML output
```

### 6. SQL Injection (N/A)
Not applicable - no SQL database used

## 🔄 Post-Deploy Verification

### Check Security Headers
```bash
curl -I https://your-domain.com/

# Expected headers:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# X-XSS-Protection: 1; mode=block
# Strict-Transport-Security: max-age=31536000 (if using HSTS)
```

### Check SSL/TLS Configuration
```bash
# Use SSL Labs
https://www.ssllabs.com/ssltest/analyze.html?d=your-domain.com

# Expected grade: A or A+
```

### Check Logs
```bash
# SSH to EC2 instance
ssh -i your-key.pem ubuntu@your-instance

# Check security logs
tail -f /opt/dou-monitor/logs/security.log

# Check system logs
sudo journalctl -u dou-monitor -f

# Check auth logs
sudo tail -f /var/log/auth.log
```

## 📊 Ongoing Security Maintenance

### Daily
- [ ] Review security.log for suspicious activity
- [ ] Check CloudWatch alarms

### Weekly
- [ ] Review failed login attempts
- [ ] Check disk usage and rotate logs
- [ ] Backup .env file (encrypted)

### Monthly
- [ ] Run `pip-audit` and update dependencies
- [ ] Review IAM permissions (principle of least privilege)
- [ ] Test disaster recovery (restore from backup)
- [ ] Review and rotate secrets

### Quarterly
- [ ] Penetration testing (automated or manual)
- [ ] Security audit review
- [ ] Update SSL certificates (if not using auto-renewal)
- [ ] Review and update Security Groups

## 🆘 Incident Response

### If Breach Detected

1. **Isolate**: Remove instance from load balancer
2. **Investigate**: Analyze logs for attack vector
3. **Remediate**: Patch vulnerability, rotate all secrets
4. **Restore**: Deploy clean instance from known-good snapshot
5. **Document**: Create post-mortem report

### Emergency Contacts
- AWS Support: https://console.aws.amazon.com/support/
- Security hotline: [Your contact info]

## ✅ Final Checklist

Before going live:

- [ ] Completed ALL items in CRITICAL section
- [ ] Completed ALL AWS Infrastructure Security items
- [ ] Ran ALL Security Testing commands
- [ ] Verified security headers with curl
- [ ] SSL grade A or A+ from SSL Labs
- [ ] Monitoring and alerts configured
- [ ] Incident response plan documented
- [ ] Team trained on security procedures

**Status:** ⬜ Not Ready | ✅ Production Ready

---

**Last Updated:** [Date]  
**Reviewed By:** [Name]  
**Next Review:** [Date + 90 days]
