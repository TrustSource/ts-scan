<?php

namespace Acme\Inventory;

use Psr\Log\LoggerInterface;

class InventoryService
{
    public function __construct(private LoggerInterface $logger)
    {
    }

    public function count(array $items): int
    {
        $this->logger->info('Counting inventory items');

        return count($items);
    }
}
