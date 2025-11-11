export function formatMyDate(dateString: string): string {
	// An array of short month names.
	const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

	// Helper function to get the ordinal suffix for the day (st, nd, rd, th).
	const getOrdinalSuffix = (day: number) => {
		if (day > 3 && day < 21) return "th"; // for 4-20
		switch (day % 10) {
			case 1:
				return "st";
			case 2:
				return "nd";
			case 3:
				return "rd";
			default:
				return "th";
		}
	};

	// Create a Date object. Appending 'T00:00:00' ensures it's parsed as local time.
	const date = new Date(dateString + "T00:00:00");

	const day = date.getDate();
	const dayWithSuffix = day + getOrdinalSuffix(day);
	const monthName = months[date.getMonth()];
	const year = date.getFullYear();

	return `${dayWithSuffix} ${monthName}, ${year}`;
}
export const CHART_TOOLTIP_STYLE = {
	contentStyle: {
		backgroundColor: "var(--card)",
		border: "1px solid rgba(82, 82, 91, 0.4)",
		borderRadius: "8px",
		boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
	},
	labelStyle: { color: "var(--accent)", fontWeight: "bold", marginBottom: "4px" },
	itemStyle: { color: "var(--muted-foreground)" },
};
