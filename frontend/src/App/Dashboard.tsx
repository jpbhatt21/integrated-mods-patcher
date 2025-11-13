import { motion } from "motion/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";

import { LogOut, RefreshCwIcon, Activity, Play, Square, TimerResetIcon, FileCogIcon, Settings2Icon, GamepadIcon, SplitIcon, PauseIcon, PickaxeIcon, ActivityIcon, ScrollTextIcon } from "lucide-react";

import type { DashboardProps } from "@/utils/types";
import { useEffect, useState } from "react";
import { apiClient } from "@/utils/api";
import Title from "./Title";

export function Dashboard({ onLogout }: DashboardProps) {
	const [state, setState] = useState<any>({
		current_task: "Unknown",
		progress: {
			categories_done: 0,
			categories_total: 41,
			category: {
				done: 0,
				name: "",
				total: 0,
			},
			files: {
				//name:{}
			},
			mods: {
				//name:{total:0, done:0}
			},
			mods_done: 0,
			mods_total: 0,
			total_files_processed: 0,
		},
	});

	// Control states
	const [game, setGame] = useState<string>(() => localStorage.getItem("game") || "WW");
	const [threads, setThreads] = useState<number>(() => parseInt(localStorage.getItem("threads") || "8"));
	const [sleep, setSleep] = useState<number>(() => parseFloat(localStorage.getItem("sleep") || "1"));
	const [delay, setDelay] = useState<number>(() => parseFloat(localStorage.getItem("delay") || "1"));
	const [mode, setMode] = useState<string>(() => localStorage.getItem("mode") || "scrape");
	const [isRunning, setIsRunning] = useState<boolean>(false);
	const [liveStats, setLiveStats] = useState<boolean>(() => (localStorage.getItem("liveStats") === "false" ? false : true));

	// Persist state changes to localStorage
	useEffect(() => {
		localStorage.setItem("game", game);
	}, [game]);

	useEffect(() => {
		localStorage.setItem("threads", threads.toString());
	}, [threads]);

	useEffect(() => {
		localStorage.setItem("sleep", sleep.toString());
	}, [sleep]);

	useEffect(() => {
		localStorage.setItem("delay", delay.toString());
	}, [delay]);

	useEffect(() => {
		localStorage.setItem("mode", mode);
	}, [mode]);

	useEffect(() => {
		localStorage.setItem("liveStats", liveStats.toString());
	}, [liveStats]);

	useEffect(() => {
		// Fetch initial data or perform setup here
		apiClient.status().then((data) => {
			if (data.success) setState(data.status);
		});
	}, []);

	useEffect(() => {
		if (!liveStats) return;

		const interval = setInterval(() => {
			apiClient.status().then((data) => {
				if (data.success) {
					setState(data.status);
					if (data.status.current_task === "Finished" || data.status.current_task === "Cancelled" || data.status.current_task === "Idle") {
						setIsRunning(false);
					} else {
						setIsRunning(true);
					}
				}
			});
		}, delay * 1000);

		return () => clearInterval(interval);
	}, [liveStats, delay]);

	const progress = state.progress;
	const categoryProgress = progress.categories_done > 0 ? (progress.categories_done / progress.categories_total) * 100 : 0;
	const modsProgress = progress.mods_total > 0 ? (progress.mods_done / progress.mods_total) * 100 : 0;
	const logs = state.logs || [];

	const handleStart = () => {
		setIsRunning(true);
		apiClient.start(mode, game, threads, sleep).then((data) => {
			if (data.success && data.status) {
				setState(data.status);
			} else if (!data.success) {
				setIsRunning(false);
			}
		});
	};

	const handleStop = () => {
		apiClient.stop();
	};

	return (
		<div className="min-h-screen bg-card/80">
			{/* Header */}
			<motion.header initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="sticky top-0 z-50 border-b backdrop-blur bg-card/20">
				<div className="container mx-auto px-4 py-3 flex items-center justify-between">
					<Title />

					<Button variant="outline" size="sm" onClick={onLogout} className="flex text-accent py-5 items-center space-x-2">
						<LogOut className="w-4 h-4" />
						<span>Logout</span>
					</Button>
				</div>
			</motion.header>

			{/* Main Content - Split Layout */}
			<main className="container mx-auto px-4 py-4">
				<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
					{/* Top-left */}
					<div className="space-y-4">
						<motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
							<Card className="sticky top-24">
								<CardHeader className="flex justify-between items-center">
									<CardTitle className="flex gap-2 items-center text-lg text-accent ">
										<Activity className="w-5 h-5" />
										Stats
									</CardTitle>
									<Button
										variant="outline"
										size="sm"
										onClick={() => {
											apiClient.status().then((data) => {
												if (data.success) setState(data.status);
											});
										}}>
										<RefreshCwIcon className="w-4 text-accent h-4" />
									</Button>
								</CardHeader>
								<CardContent className="grid grid-cols-1 lg:grid-cols-2 gap-4">
									<Card className="border-0 bg-input/10">
										<CardHeader>
											<CardTitle className="flex items-center gap-2">
												<TimerResetIcon className="w-5 h-5" />
												Status
											</CardTitle>
										</CardHeader>
										<CardContent>
											<div className="flex items-center justify-between">
												<span className="text-3xl font-bold text-primary">{isRunning && ["Idle", "Finished", "Cancelled"].includes(state.current_task) ? "Running" : state.current_task}</span>
											</div>
										</CardContent>
									</Card>
									<Card className="border-0 bg-input/10">
										<CardHeader>
											<CardTitle className="flex items-center gap-2">
												<FileCogIcon className="w-5 h-5" />
												Files Processed
											</CardTitle>
										</CardHeader>
										<CardContent>
											<div className="flex items-center justify-between">
												<div className="flex items-baseline gap-2">
													<span className="text-3xl font-bold">{progress.total_files_processed}</span>
													<span className="text-muted-foreground">files</span>
												</div>
											</div>
										</CardContent>
									</Card>
									<Card className="border-0 bg-input/10">
										<CardHeader>
											<CardTitle className="flex items-center gap-2">
												<FileCogIcon className="w-5 h-5" />
												{state.current_task === "Fixing" ? "File Batch" : state.current_task === "Mapping" ? "Mods Used" : "Categories"}
											</CardTitle>
										</CardHeader>
										<CardContent>
											<div className="space-y-2">
												<div className="flex items-baseline gap-2">
													<span className="text-3xl font-bold">{progress.categories_done}</span>
													<span className="text-muted-foreground">/ {progress.categories_total}</span>
												</div>
												<div className="w-full bg-secondary rounded-full h-2.5">
													<div className="bg-accent h-2.5 rounded-full transition-all duration-300" style={{ width: `${categoryProgress}%` }}></div>
												</div>
												<p className="text-xs text-muted-foreground">{state.current_task === "Fixing" ? `${categoryProgress.toFixed(1)}% complete` : "⠀"}</p>
											</div>
										</CardContent>
									</Card>
									<Card className="border-0 bg-input/10">
										<CardHeader>
											<CardTitle className="flex items-center gap-2">
												<FileCogIcon className="w-5 h-5" />
												Mods
											</CardTitle>
										</CardHeader>
										<CardContent>
											<div className="space-y-2">
												<div className="flex items-baseline gap-2">
													<span className="text-3xl font-bold">{progress.mods_done}</span>
													<span className="text-muted-foreground">/ {progress.mods_total}</span>
												</div>
												<div className="w-full bg-secondary rounded-full h-2.5">
													<div className="bg-accent h-2.5 rounded-full transition-all duration-300" style={{ width: `${modsProgress}%` }}></div>
												</div>
												<p className="text-xs text-muted-foreground">{isRunning ? `${modsProgress.toFixed(1)}% complete` : "⠀"}</p>
											</div>
										</CardContent>
									</Card>
								</CardContent>
							</Card>
						</motion.div>

						<motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
							<Card className="sticky top-24">
								<CardHeader className="flex justify-between items-center">
									<CardTitle className="flex gap-2 items-center text-lg text-accent ">
										<Settings2Icon className="w-5 h-5" />
										Config
									</CardTitle>
								</CardHeader>
								<CardContent className="grid grid-cols-1 lg:grid-cols-2 gap-4">
									{/* Game Selection */}
									<Card className="border-0  h-20 justify-center bg-input/10">
										<CardContent className="flex gap-4">
											<CardTitle className="flex items-center gap-2">
												<GamepadIcon className="w-5 h-5" />
												Game
											</CardTitle>
											<Select value={game} onValueChange={setGame}>
												<SelectTrigger id="game" disabled={isRunning} className="bg-button text-foreground/90 duration-200 transition-opacity">
													<SelectValue placeholder="Select a game" />
												</SelectTrigger>
												<SelectContent>
													<SelectItem value="WW">Wuthering Waves</SelectItem>
													<SelectItem value="GI">Genshin Impact</SelectItem>
													<SelectItem value="ZZ">Zenless Zone Zero</SelectItem>
												</SelectContent>
											</Select>
										</CardContent>
									</Card>
									<Card className="border-0  h-20 justify-center bg-input/10">
										<CardContent className="flex gap-4">
											<CardTitle className="flex items-center gap-2">
												<PickaxeIcon className="w-5 h-5" />
												Action
											</CardTitle>
											<Select value={mode} onValueChange={setMode}>
												<SelectTrigger id="mode" disabled={isRunning} className="bg-button text-foreground/90 duration-200 transition-opacity">
													<SelectValue placeholder="Select an action" />
												</SelectTrigger>
												<SelectContent>
													<SelectItem value="scrape">Scrape</SelectItem>
													<SelectItem value="update">Update</SelectItem>
													<SelectItem value="fix">Fix</SelectItem>
													<SelectItem value="map">Map Hashes</SelectItem>
												</SelectContent>
											</Select>
										</CardContent>
									</Card>
									<Card className="border-0  h-20 justify-center bg-input/10">
										<CardContent className="flex gap-4">
											<CardTitle className="flex items-center gap-2">
												<SplitIcon className="w-5 h-5" />
												Threads
											</CardTitle>
											<Slider id="max-threads" disabled={isRunning} className="duration-200 transition-opacity" min={0} max={16} step={1} value={[threads]} onValueChange={(value) => setThreads(value[0])} />
											<span className="text-sm text-muted-foreground">{threads}</span>
										</CardContent>
									</Card>

									<Card className="border-0  h-20 justify-center bg-input/10">
										<CardContent className="flex gap-4">
											<CardTitle className="flex items-center gap-2">
												<PauseIcon className="w-5 h-5" />
												Sleep
											</CardTitle>
											<Slider id="sleep" disabled={isRunning} className="duration-200 transition-opacity" min={0} max={10} step={0.5} value={[sleep]} onValueChange={(value) => setSleep(value[0])} />
											<span className="text-sm text-muted-foreground">{sleep}s</span>
										</CardContent>
									</Card>

									<Card className="border-0  h-20 justify-center bg-input/10">
										<CardContent className="flex gap-4">
											<CardTitle className="flex min-w-fit items-center gap-2">
												<ActivityIcon className="w-5 h-5" />
												Live Stats
											</CardTitle>
											<Slider
												id="delay"
												min={0}
												max={5}
												step={0.5}
												value={[delay]}
												onValueChange={(value) => {
													if (value[0] === 0) setLiveStats(false);
													else setLiveStats(true);
													setDelay(value[0]);
												}}
											/>

											<span className="text-sm max-w-4 text-muted-foreground">{liveStats ? `${delay}s` : "Off"}</span>
										</CardContent>
									</Card>

									{/* Start/Stop Button */}
									<div className="space-y-2">
										<Button className="w-full h-20 text-lg rounded-xl bg-input/10" size="lg" onClick={isRunning ? handleStop : handleStart}>
											{isRunning ? (
												<>
													<Square className="min-w-5 min-h-5 mr-2" />
													Stop
												</>
											) : (
												<>
													<Play className="min-w-5 min-h-5 mr-2" />
													Start
												</>
											)}
										</Button>
									</div>
								</CardContent>
							</Card>
						</motion.div>
					</div>
					<div className="space-y-4 h-full">
						<motion.div className="h-full" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
							<Card className="sticky flex h-full top-24">
								<CardHeader className="flex justify-between items-center">
									<CardTitle className="flex gap-2 items-center text-lg text-accent ">
										<ScrollTextIcon className="w-5 h-5" />
										Logs
									</CardTitle>
								</CardHeader>
								<CardContent className="h-175 mr-2 overflow-y-scroll thin p-2">
									<div className="space-y-2">
										{logs.length === 0 && <p className="text-sm text-muted-foreground">No logs available.</p>}
										{logs.map((log: string, index: number) => (
											<p
												key={index}
												className="text-xs font-mono text-muted-foreground"
												style={{
													color: log.includes("[ERROR]") ? "var(--destructive)" : "",
												}}>
												{log}
											</p>
										))}
									</div>
								</CardContent>
							</Card>
						</motion.div>
					</div>
				</div>
			</main>
		</div>
	);
}
