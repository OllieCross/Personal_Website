# OllieCross - Portfolio & Services

Personal portfolio website for OllieCross, a multidisciplinary creative technologist working at the intersection of light, motion, and code - from intimate club nights to large-scale festival productions.

## Sections

- **Hero** - Introduction with name, tagline, and service pills
- **About** - Bio, 8+ years experience, 200+ events, stats
- **Credits** - Past clients and collaborators
- **Lights** - Lighting direction and LD programming work
- **Visuals** - VJ / live visuals work
- **Stage** - Stage design and plotting
- **IT** - Development and technical services
- **Contact** - Enquiry form

## Stack

Single-page HTML/CSS/JS - no build step, no dependencies. Served via nginx.

## Deployment

The site runs on a separate host (`<WEB_HOST>`) behind a Traefik reverse proxy (`<TRAEFIK_HOST>`). Traefik handles TLS termination and forwards plain HTTP to the nginx container.

### On the web host

```bash
docker compose up -d --build
```

nginx listens on port 80, bound to localhost only. Traefik reaches it over the LAN.

### On the Traefik host

Add the router, middleware, and service block from `dynamic_conf.yml` to your existing Traefik dynamic config. No restart needed - Traefik picks up the change live.

```text
Client -> 443 HTTPS (Traefik, TLS) -> <WEB_HOST>:80 (nginx, plain HTTP)
```
