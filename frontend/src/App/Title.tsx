import logo from "/logo.png"
function Title({className}: {className?: string}) {
	return (
		<div className={`min-h-16 min-w-16 flex items-center justify-center h-16 gap-5 p-0 ${className}`}>
			<div
				id="WWMMLogo"
				className="aspect-square h-10"
				style={{
					background: "url(" + logo + ")",
					backgroundSize: "contain",
					backgroundRepeat: "no-repeat",
					backgroundPosition: "center",
				}}></div>
			<div className="flex flex-col wuwa-ft w-24 text-center duration-200 ease-linear">
				<label className="text-2xl text-[#eaeaea] min-w-fit font-bold">WuWa</label>
				<label className="min-w-fit text-accent/75 text-sm">Mod Manager</label>
			</div>
		</div>
	);
}

export default Title;
