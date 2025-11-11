import { useState } from "react";
import { motion } from "motion/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { apiClient } from "@/utils/api";
import type { LoginProps } from "@/utils/types";
import Title from "./Title";

export function Login({ onLogin }: LoginProps) {
	const [username, setUsername] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState("");
	const [isLoading, setIsLoading] = useState(false);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setIsLoading(true);
		setError("");

		try {
			const result = await apiClient.login(username, password);

			if (result.success) {
				onLogin();
			} else {
				setError(result.error || "Invalid username or password");
			}
		} catch (error) {
			setError("Login failed. Please check your connection and try again.");
		}

		setIsLoading(false);
	};

	return (
		<div className="min-h-screen flex items-center justify-center bg-sidebar/70">
			<motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="w-full max-w-md px-4">
				<Card className="shadow-xl bg-transparent border-0 rounded-md py-4">
					<CardHeader>
						<CardTitle className="text-2xl pb-4 border-b font-bold text-center">
							<Title className="scale-120" />
						</CardTitle>
						<CardDescription className="text-center mt-2 wuwa-ft text-muted-foreground">Admin Dashboard</CardDescription>
					</CardHeader>
					<CardContent>
						<form onSubmit={handleSubmit} className="space-y-4">
							<div className="space-y-2">
								{/* <Label htmlFor="username">Username</Label> */}
								<Input id="username" type="text" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} required className="transition-all duration-200 focus:ring-2 focus:ring-blue-500" />
							</div>
							<div className="space-y-2">
								{/* <Label htmlFor="password">Password</Label> */}
								<Input id="password" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required className="transition-all duration-200 focus:ring-2 focus:ring-blue-500" />
							</div>

							{error && (
								<motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.2 }}>
									<Alert variant="destructive">
										<AlertDescription>{error}</AlertDescription>
									</Alert>
								</motion.div>
							)}

							<Button type="submit" className="w-full bg-accent text-background" disabled={isLoading}>
								{isLoading ? <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: "linear" }} className="w-4 h-4 border-2 border-white text-background border-t-transparent rounded-full" /> : "Sign In"}
							</Button>
						</form>
					</CardContent>
				</Card>

				{/* <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5, duration: 0.5 }}
          className="mt-4 text-center text-sm text-neutral-600 dark:text-neutral-400"
        >
          <p>Default credentials: admin / password123</p>
          <p className="text-xs mt-1">Configure with VITE_DASHBOARD_USERNAME and VITE_DASHBOARD_PASSWORD environment variables</p>
        </motion.div> */}
			</motion.div>
		</div>
	);
}
