import { ArenaPortfolioSetupsTab } from '../components/arena/ArenaPortfolioSetupsTab';

/**
 * Global portfolio setup management page.
 */
export const PortfolioSetups = () => {
  return (
    <div className="container mx-auto px-6 py-6 md:py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Portfolio Setups</h1>
        <p className="text-muted-foreground">
          Reusable portfolio constraints for Arena simulations
        </p>
      </div>

      <ArenaPortfolioSetupsTab />
    </div>
  );
};
