import './globals.css';
import { Inter } from 'next/font/google';
import { motion } from 'framer-motion';

const inter = Inter({ subsets: ['latin'] });

// Define global dark mode theme setup
export const metadata = {
  title: "Arjun Mehta | AI & Agent Systems Portfolio",
  description: "Portfolio of an AI Engineer and Agent Systems Builder.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-gray-950 text-gray-100 antialiased scroll-smooth`}>
        {/* Framer Motion for overall page fade in effect */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="min-h-screen"
        >
          {children}
        </motion.div>
      </body>
    </html>
  );
}