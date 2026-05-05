import { getPermalink, getBlogPermalink } from './utils/permalinks';

export const headerData = {
  links: [
    {
      text: 'Guides',
      links: [
        { text: 'All Guides', href: getBlogPermalink() },
        { text: 'Prop Firms', href: getPermalink('prop-firms', 'category') },
        { text: 'Forex Brokers', href: getPermalink('forex-brokers', 'category') },
        { text: 'Strategies', href: getPermalink('strategies', 'category') },
        { text: 'Tools', href: getPermalink('tools', 'category') },
        { text: 'Education', href: getPermalink('education', 'category') },
        { text: 'Crypto', href: getPermalink('crypto', 'category') },
      ],
    },
    { text: 'About', href: getPermalink('/about') },
    { text: 'Contact', href: getPermalink('/contact') },
  ],
  actions: [],
};

export const footerData = {
  links: [
    {
      title: 'Categories',
      links: [
        { text: 'Prop Firms', href: getPermalink('prop-firms', 'category') },
        { text: 'Forex Brokers', href: getPermalink('forex-brokers', 'category') },
        { text: 'Strategies', href: getPermalink('strategies', 'category') },
        { text: 'Tools', href: getPermalink('tools', 'category') },
        { text: 'Education', href: getPermalink('education', 'category') },
        { text: 'Crypto', href: getPermalink('crypto', 'category') },
      ],
    },
    {
      title: 'Resources',
      links: [
        { text: 'All Guides', href: getBlogPermalink() },
      ],
    },
    {
      title: 'Company',
      links: [
        { text: 'About', href: getPermalink('/about') },
        { text: 'Contact', href: getPermalink('/contact') },
        { text: 'Blog', href: getBlogPermalink() },
      ],
    },
    {
      title: 'Legal',
      links: [
        { text: 'Privacy Policy', href: getPermalink('/privacy') },
        { text: 'Terms & Conditions', href: getPermalink('/terms') },
        { text: 'Affiliate Disclosure', href: getPermalink('/disclosure') },
      ],
    },
  ],
  secondaryLinks: [
    { text: 'Privacy Policy', href: getPermalink('/privacy') },
    { text: 'Terms', href: getPermalink('/terms') },
    { text: 'Disclosure', href: getPermalink('/disclosure') },
  ],
  socialLinks: [],
  footNote: `
    © ${new Date().getFullYear()} TradingHub. All rights reserved.
  `,
};
