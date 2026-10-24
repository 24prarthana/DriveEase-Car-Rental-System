/* DriveEase customer login migration.
   Safe additive change: does not delete or overwrite existing customer, car, or booking rows.
   Run this script once in SSMS with CarRentalDB selected. */
USE CarRentalDB;
GO
IF OBJECT_ID(N'dbo.CustomerAccounts', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.CustomerAccounts
    (
        CustomerID INT NOT NULL PRIMARY KEY,
        PasswordHash NVARCHAR(255) NOT NULL,
        CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_CustomerAccounts_CreatedAt DEFAULT SYSDATETIME(),
        CONSTRAINT FK_CustomerAccounts_Customers FOREIGN KEY (CustomerID)
            REFERENCES dbo.Customers(CustomerID)
    );
END;
GO
PRINT 'CustomerAccounts table is ready. Existing customer and booking records were preserved.';
GO
